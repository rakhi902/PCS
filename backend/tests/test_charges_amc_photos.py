"""Focused regression tests for Iteration 7 bug fixes:
- Manager can POST charges on services and contract_amount on AMC (response reflects submitted values)
- Manager sees charges in GET responses
- Technician still never sees charges
- PATCH /api/services/{id} status=completed enforces before+after photos for non-admin (400 when missing)
- Admin bypass for status=completed without photos
- Technician POST /api/services/{id}/complete without photos → 400
- Regression: Termite auto-reminder still created via /complete
"""
import os
import io
import uuid
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = (
    os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or os.environ.get("EXPO_BACKEND_URL")
    or "http://localhost:8001"
).rstrip("/")

API = f"{BASE_URL}/api"


def _login(username, pin):
    r = requests.post(f"{API}/auth/login", json={"username": username, "pin": pin}, timeout=30)
    assert r.status_code == 200, f"login {username} failed: {r.status_code} {r.text}"
    return r.json()["token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _reset_admin_pin():
    """Admin might have must_change_pin. Rotate it to 1234 (idempotent)."""
    import bcrypt
    from pymongo import MongoClient
    mc = MongoClient(os.environ["MONGO_URL"])
    mc[os.environ["DB_NAME"]].users.update_one(
        {"username": "admin"},
        {"$set": {
            "pin_hash": bcrypt.hashpw(b"1234", bcrypt.gensalt()).decode(),
            "must_change_pin": False,
            "active": True,
        }},
    )
    mc.close()


@pytest.fixture(scope="module")
def ctx():
    _reset_admin_pin()
    admin = _login("admin", "1234")

    suffix = uuid.uuid4().hex[:6]
    mgr_user = f"tmgr_{suffix}"
    tech_user = f"ttech_{suffix}"

    # Create manager + technician
    r = requests.post(f"{API}/users", headers=_h(admin),
                      json={"username": mgr_user, "name": "TEST Mgr", "role": "manager", "pin": "1111"})
    assert r.status_code == 200, r.text
    mgr_id = r.json()["id"]

    r = requests.post(f"{API}/users", headers=_h(admin),
                      json={"username": tech_user, "name": "TEST Tech", "role": "technician", "pin": "1111"})
    assert r.status_code == 200, r.text
    tech_id = r.json()["id"]

    # First login → must_change_pin. Change to 2222.
    mgr_tok0 = _login(mgr_user, "1111")
    requests.post(f"{API}/auth/change-pin", headers=_h(mgr_tok0), json={"pin": "2222"})
    tech_tok0 = _login(tech_user, "1111")
    requests.post(f"{API}/auth/change-pin", headers=_h(tech_tok0), json={"pin": "2222"})

    mgr = _login(mgr_user, "2222")
    tech = _login(tech_user, "2222")

    # Create a customer
    r = requests.post(f"{API}/customers", headers=_h(admin),
                      json={"name": f"TEST_Cust_{suffix}", "mobile": "9990000000"})
    assert r.status_code == 200, r.text
    cust_id = r.json()["id"]

    return {
        "admin": admin, "mgr": mgr, "tech": tech,
        "mgr_id": mgr_id, "tech_id": tech_id, "cust_id": cust_id, "suffix": suffix,
    }


# ------------------- Manager charges on services -------------------
class TestManagerCharges:
    def test_manager_post_service_with_charges(self, ctx):
        r = requests.post(f"{API}/services", headers=_h(ctx["mgr"]), json={
            "customer_id": ctx["cust_id"], "service_type": "Cockroach",
            "scheduled_date": "2026-02-01T09:00:00+00:00", "charges": 1500,
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("charges") == 1500, f"POST response should reflect charges=1500, got {data.get('charges')}"
        ctx["mgr_service_id"] = data["id"]

    def test_manager_get_services_includes_charges(self, ctx):
        r = requests.get(f"{API}/services", headers=_h(ctx["mgr"]))
        assert r.status_code == 200
        arr = r.json()
        target = next((s for s in arr if s["id"] == ctx["mgr_service_id"]), None)
        assert target is not None, "manager should see own-created service"
        assert target.get("charges") == 1500, f"manager GET must show charges=1500, got {target.get('charges')}"

    def test_manager_get_service_detail_includes_charges(self, ctx):
        r = requests.get(f"{API}/services/{ctx['mgr_service_id']}", headers=_h(ctx["mgr"]))
        assert r.status_code == 200
        assert r.json().get("charges") == 1500

    def test_manager_patch_charges_persists(self, ctx):
        r = requests.patch(f"{API}/services/{ctx['mgr_service_id']}", headers=_h(ctx["mgr"]),
                           json={"charges": 2500})
        assert r.status_code == 200, r.text
        r = requests.get(f"{API}/services/{ctx['mgr_service_id']}", headers=_h(ctx["mgr"]))
        assert r.json().get("charges") == 2500

    def test_technician_never_sees_charges_in_list(self, ctx):
        # Assign the service to tech first (admin)
        requests.patch(f"{API}/services/{ctx['mgr_service_id']}", headers=_h(ctx["admin"]),
                       json={"technician_id": ctx["tech_id"]})
        r = requests.get(f"{API}/services", headers=_h(ctx["tech"]))
        assert r.status_code == 200
        for s in r.json():
            assert "charges" not in s, f"technician list must NOT include charges, found in {s['id']}"

    def test_technician_never_sees_charges_in_detail(self, ctx):
        r = requests.get(f"{API}/services/{ctx['mgr_service_id']}", headers=_h(ctx["tech"]))
        assert r.status_code == 200
        assert "charges" not in r.json(), "technician detail must NOT include charges"

    def test_admin_sees_charges(self, ctx):
        r = requests.get(f"{API}/services/{ctx['mgr_service_id']}", headers=_h(ctx["admin"]))
        assert r.status_code == 200
        assert r.json().get("charges") == 2500


# ------------------- Manager contract_amount on AMC -------------------
class TestManagerAMC:
    def test_manager_post_amc_with_contract_amount(self, ctx):
        r = requests.post(f"{API}/amc", headers=_h(ctx["mgr"]), json={
            "customer_id": ctx["cust_id"], "service_type": "Cockroach",
            "start_date": "2026-02-01T00:00:00+00:00", "end_date": "2026-05-01T00:00:00+00:00",
            "frequency": "monthly", "contract_amount": 12000,
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("contract_amount") == 12000, \
            f"POST /amc response must reflect contract_amount=12000, got {data.get('contract_amount')}"
        assert data.get("generated", 0) >= 1, "AMC should generate services"
        ctx["mgr_amc_id"] = data["id"]

    def test_manager_get_amc_list_includes_contract_amount(self, ctx):
        r = requests.get(f"{API}/amc", headers=_h(ctx["mgr"]))
        assert r.status_code == 200
        target = next((a for a in r.json() if a["id"] == ctx["mgr_amc_id"]), None)
        assert target is not None
        assert target.get("contract_amount") == 12000

    def test_amc_generated_services_persisted(self, ctx):
        r = requests.get(f"{API}/amc/{ctx['mgr_amc_id']}", headers=_h(ctx["mgr"]))
        assert r.status_code == 200
        body = r.json()
        assert body["amc"]["contract_amount"] == 12000
        assert len(body["services"]) >= 1

    def test_admin_amc_list_includes_contract_amount(self, ctx):
        r = requests.get(f"{API}/amc", headers=_h(ctx["admin"]))
        assert r.status_code == 200
        target = next((a for a in r.json() if a["id"] == ctx["mgr_amc_id"]), None)
        assert target is not None
        assert target.get("contract_amount") == 12000


# ------------------- Photo enforcement on PATCH status=completed -------------------
class TestCompletePhotoEnforcement:
    @pytest.fixture(scope="class")
    def svc_ids(self, ctx):
        # Create 3 services (one for manager attempt, one for admin bypass, one baseline)
        ids = {}
        for key in ("for_mgr_400", "for_admin_bypass"):
            r = requests.post(f"{API}/services", headers=_h(ctx["admin"]), json={
                "customer_id": ctx["cust_id"], "service_type": "Cockroach",
                "scheduled_date": "2026-02-05T09:00:00+00:00", "charges": 500,
                "technician_id": ctx["tech_id"],
            })
            assert r.status_code == 200, r.text
            ids[key] = r.json()["id"]
        return ids

    def test_manager_patch_complete_without_photos_returns_400(self, ctx, svc_ids):
        sid = svc_ids["for_mgr_400"]
        r = requests.patch(f"{API}/services/{sid}", headers=_h(ctx["mgr"]),
                           json={"status": "completed"})
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"
        msg = (r.json().get("detail") or "").lower()
        assert "photo" in msg, f"error message should mention photos: {r.text}"
        # State should remain previous (assigned)
        r = requests.get(f"{API}/services/{sid}", headers=_h(ctx["admin"]))
        assert r.json().get("status") != "completed", "status must NOT flip to completed on 400"

    def test_admin_patch_complete_without_photos_ok(self, ctx, svc_ids):
        sid = svc_ids["for_admin_bypass"]
        r = requests.patch(f"{API}/services/{sid}", headers=_h(ctx["admin"]),
                           json={"status": "completed"})
        assert r.status_code == 200, f"admin bypass expected 200, got {r.status_code} {r.text}"
        r = requests.get(f"{API}/services/{sid}", headers=_h(ctx["admin"]))
        assert r.json().get("status") == "completed"

    def test_technician_complete_endpoint_without_photos_returns_400(self, ctx, svc_ids):
        sid = svc_ids["for_mgr_400"]  # still not completed, has no photos, assigned to tech
        r = requests.post(f"{API}/services/{sid}/complete", headers=_h(ctx["tech"]), json={})
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"
        assert "photo" in (r.json().get("detail") or "").lower()


# ------------------- Regression: Termite auto-reminder still fires -------------------
class TestTermiteAutoReminderRegression:
    def test_termite_reminder_created_via_complete_endpoint(self, ctx):
        # Fresh Termite service assigned to tech
        r = requests.post(f"{API}/services", headers=_h(ctx["admin"]), json={
            "customer_id": ctx["cust_id"], "service_type": "Termite",
            "scheduled_date": "2026-02-10T09:00:00+00:00", "technician_id": ctx["tech_id"],
        })
        assert r.status_code == 200, r.text
        sid = r.json()["id"]

        # Upload before + after photos as tech
        for phase in ("before", "after"):
            files = {"file": ("t.jpg", io.BytesIO(b"\xff\xd8\xffimg"), "image/jpeg")}
            r = requests.post(f"{API}/services/{sid}/photos", headers=_h(ctx["tech"]),
                              data={"phase": phase}, files=files)
            assert r.status_code == 200, f"photo upload {phase} failed: {r.text}"

        # Complete via /complete
        r = requests.post(f"{API}/services/{sid}/complete", headers=_h(ctx["tech"]), json={})
        assert r.status_code == 200, r.text

        # Verify Termite reminder was created for this customer
        r = requests.get(f"{API}/reminders", headers=_h(ctx["admin"]))
        assert r.status_code == 200
        rems = r.json()
        match = [x for x in rems if x.get("customer_id") == ctx["cust_id"]
                 and x.get("service_type") == "Termite"
                 and x.get("auto_source") == "termite_annual"]
        assert len(match) >= 1, "Termite annual auto-reminder must exist after /complete"
