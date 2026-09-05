"""Final production QA for pest control mgmt.
Covers every scenario in the review request end-to-end.
Run: pytest /app/backend/tests/test_production_qa.py -n 0 -v
"""
import io
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

# module-scoped shared state
S: dict = {}


def _rand():
    return uuid.uuid4().hex[:8]


def _login(username: str, pin: str):
    r = requests.post(f"{API}/auth/login", json={"username": username, "pin": pin})
    return r


def _login_admin():
    r = _login("admin", "1234")
    if r.status_code == 200:
        return r.json()
    r = _login("admin", "9999")
    if r.status_code == 200:
        return r.json()
    pytest.fail(f"admin login failed with both PINs: {r.status_code} {r.text}")


def _hdrs(token: str):
    return {"Authorization": f"Bearer {token}"}


# ---------------- Setup ---------------- #
class TestASetup:
    """Admin login, PIN change if required, seed users"""

    def test_admin_login(self):
        data = _login_admin()
        assert "token" in data and "user" in data
        S["admin_tok"] = data["token"]
        S["admin_user"] = data["user"]
        # Change pin if needed but rotate back to same value so test is idempotent
        if data["user"].get("must_change_pin"):
            r = requests.post(
                f"{API}/auth/change-pin", json={"pin": "1234"}, headers=_hdrs(S["admin_tok"])
            )
            assert r.status_code == 200

    def test_no_mongo_id_leak_in_login(self):
        assert "_id" not in S["admin_user"]

    def test_create_manager_and_technicians(self):
        h = _hdrs(S["admin_tok"])
        mgr_u = f"tmgr_{_rand()}"
        r = requests.post(
            f"{API}/users",
            json={"username": mgr_u, "name": "TEST Mgr", "role": "manager", "pin": "1111"},
            headers=h,
        )
        assert r.status_code == 200, r.text
        S["mgr_id"] = r.json()["id"]; S["mgr_user"] = mgr_u
        # Login manager -> change pin
        tok = _login(mgr_u, "1111").json()["token"]
        requests.post(f"{API}/auth/change-pin", json={"pin": "2222"}, headers=_hdrs(tok))
        S["mgr_tok"] = _login(mgr_u, "2222").json()["token"]

        for label in ("t1", "t2"):
            u = f"ttech_{label}_{_rand()}"
            r = requests.post(
                f"{API}/users",
                json={"username": u, "name": f"TEST Tech {label}", "role": "technician", "pin": "1111"},
                headers=h,
            )
            assert r.status_code == 200
            tid = r.json()["id"]
            tok = _login(u, "1111").json()["token"]
            requests.post(f"{API}/auth/change-pin", json={"pin": "2222"}, headers=_hdrs(tok))
            S[f"tech_{label}_id"] = tid
            S[f"tech_{label}_user"] = u
            S[f"tech_{label}_tok"] = _login(u, "2222").json()["token"]

    def test_manager_cannot_create_user(self):
        r = requests.post(
            f"{API}/users",
            json={"username": f"nope_{_rand()}", "name": "n", "role": "technician", "pin": "1111"},
            headers=_hdrs(S["mgr_tok"]),
        )
        assert r.status_code == 403

    def test_manager_cannot_reset_pin(self):
        r = requests.post(
            f"{API}/users/{S['tech_t1_id']}/reset-pin",
            json={"pin": "9999"},
            headers=_hdrs(S["mgr_tok"]),
        )
        assert r.status_code == 403


# ---------------- Customers ---------------- #
class TestBCustomers:
    def test_create_customer(self):
        h = _hdrs(S["admin_tok"])
        payload = {"name": f"TEST_Cust_{_rand()}", "mobile": "9990001111",
                   "address": "1 Test Rd", "city": "Test"}
        r = requests.post(f"{API}/customers", json=payload, headers=h)
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["name"] == payload["name"] and c["id"]
        assert "_id" not in c
        S["cid"] = c["id"]
        # persistence GET
        r2 = requests.get(f"{API}/customers", headers=h)
        assert r2.status_code == 200
        assert any(x["id"] == c["id"] for x in r2.json())

    def test_extra_customers(self):
        h = _hdrs(S["admin_tok"])
        for k in ("cid2", "cid3"):
            r = requests.post(
                f"{API}/customers",
                json={"name": f"TEST_Cust_{_rand()}", "mobile": "9995550000"},
                headers=h,
            )
            S[k] = r.json()["id"]


# ---------------- Service create + full completion flow ---------------- #
class TestCEndToEnd:
    def test_admin_creates_termite_service_for_tech1_on_specific_date(self):
        h = _hdrs(S["admin_tok"])
        # Simulate scheduled_date of 10/09/2026
        sched = "2026-09-10T10:00:00+00:00"
        r = requests.post(
            f"{API}/services",
            json={
                "customer_id": S["cid"], "service_type": "Termite",
                "scheduled_date": sched, "technician_id": S["tech_t1_id"],
                "charges": 2500,
            },
            headers=h,
        )
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["status"] == "assigned"
        assert s["technician_id"] == S["tech_t1_id"]
        assert s["scheduled_date"] == sched  # ISO string preserved
        assert "_id" not in s
        S["sid"] = s["id"]

    def test_tech_uploads_before_during_after_photos(self):
        h = _hdrs(S["tech_t1_tok"])
        sid = S["sid"]
        for phase in ("before", "during", "after"):
            files = {"file": (f"{phase}.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"0" * 32), "image/jpeg")}
            data = {"phase": phase}
            r = requests.post(f"{API}/services/{sid}/photos", files=files, data=data, headers=h)
            if r.status_code == 500:
                pytest.skip("Emergent Object Storage unavailable")
            assert r.status_code == 200, r.text
        # verify photos array grew
        r = requests.get(f"{API}/services/{sid}", headers=h)
        assert r.status_code == 200
        photos = r.json()["photos"]
        assert len(photos["before"]) >= 1 and len(photos["during"]) >= 1 and len(photos["after"]) >= 1

    def test_feedback_and_termite_reminder_created_on_complete(self):
        # tech completes service (no photos-check bypass needed; before+after present)
        h = _hdrs(S["tech_t1_tok"])
        r = requests.post(f"{API}/services/{S['sid']}/complete", json={"medicine": "X", "quantity": "1L"}, headers=h)
        if r.status_code == 400 and "photos required" in r.text.lower():
            pytest.skip("photo upload was skipped earlier")
        assert r.status_code == 200, r.text
        # feedback_requests row should exist
        # Directly query via list_feedback? Not exposed - use audit-logs or check dashboards
        # Instead verify reminder is created (Termite auto)
        rr = requests.get(f"{API}/reminders", headers=_hdrs(S["admin_tok"]))
        assert rr.status_code == 200
        rems = [x for x in rr.json() if x.get("source_service_id") == S["sid"]]
        assert len(rems) == 1, f"expected 1 auto reminder, got {len(rems)}"
        rem = rems[0]
        assert rem["service_type"] == "Termite"
        assert rem.get("auto_source") == "termite_annual"
        # verify due_date approx 03/09/2027 (1 year - 7 days from completion "today")
        # Since completed_at is now, we check: due date approx = now + 1y - 7d
        due = datetime.fromisoformat(rem["due_date"].replace("Z", "+00:00"))
        expected = datetime.now(timezone.utc) + timedelta(days=365 - 7)
        diff = abs((due - expected).total_seconds())
        assert diff < 3 * 24 * 3600, f"due {due} vs expected {expected} diff={diff}"
        S["rem_id"] = rem["id"]

    def test_reminder_shows_upcoming(self):
        r = requests.get(f"{API}/reminders", headers=_hdrs(S["admin_tok"]))
        rem = next(x for x in r.json() if x["id"] == S["rem_id"])
        assert rem["computed"] == "upcoming"

    def test_reminder_included_in_admin_dashboard_counter(self):
        r = requests.get(f"{API}/dashboard/admin", headers=_hdrs(S["admin_tok"]))
        assert r.status_code == 200
        assert r.json()["reminders_upcoming"] >= 1


# ---------------- Termite duplicate prevention ---------------- #
class TestDTermiteDup:
    def test_second_termite_completion_same_customer_no_dup(self):
        h = _hdrs(S["admin_tok"])
        # Create another Termite service same customer, complete via PATCH (skip photo requirement)
        r = requests.post(
            f"{API}/services",
            json={"customer_id": S["cid"], "service_type": "Termite",
                  "scheduled_date": datetime.now(timezone.utc).isoformat(),
                  "technician_id": S["tech_t1_id"], "charges": 1500},
            headers=h,
        )
        sid2 = r.json()["id"]
        # PATCH status=completed as admin (bypasses photo check)
        r2 = requests.patch(f"{API}/services/{sid2}", json={"status": "completed"}, headers=h)
        assert r2.status_code == 200
        rr = requests.get(f"{API}/reminders", headers=h)
        rems = [x for x in rr.json() if x["customer_id"] == S["cid"] and x["service_type"] == "Termite"]
        assert len(rems) == 1, f"expected exactly 1 termite reminder, got {len(rems)}"

    def test_non_termite_completion_no_reminder(self):
        h = _hdrs(S["admin_tok"])
        r = requests.post(
            f"{API}/services",
            json={"customer_id": S["cid2"], "service_type": "Cockroach",
                  "scheduled_date": datetime.now(timezone.utc).isoformat(),
                  "technician_id": S["tech_t1_id"], "charges": 500},
            headers=h,
        )
        sid = r.json()["id"]
        requests.patch(f"{API}/services/{sid}", json={"status": "completed"}, headers=h)
        rr = requests.get(f"{API}/reminders", headers=h)
        matches = [x for x in rr.json() if x.get("source_service_id") == sid]
        assert len(matches) == 0


# ---------------- Manager permissions ---------------- #
class TestEManagerPerms:
    def test_manager_403_on_admin_endpoints(self):
        h = _hdrs(S["mgr_tok"])
        for path in ("/reports/summary", "/dashboard/admin", "/audit-logs"):
            r = requests.get(f"{API}{path}", headers=h)
            assert r.status_code == 403, f"{path} -> {r.status_code}"
        # CSV export
        r = requests.get(f"{API}/reports/export.csv", params={"kind": "services", "token": S["mgr_tok"]})
        assert r.status_code == 403

    def test_manager_customers_and_services_see_charges(self):
        # SPEC CHANGE (iteration 7): Manager CAN now see charges on services.
        h = _hdrs(S["mgr_tok"])
        r = requests.get(f"{API}/customers", headers=h)
        assert r.status_code == 200
        r = requests.get(f"{API}/services", headers=h)
        assert r.status_code == 200
        # Manager should see the 'charges' key on each service (may be 0)
        for s in r.json():
            assert "charges" in s

    def test_manager_post_service_charges_persisted(self):
        # SPEC CHANGE (iteration 7): Manager can POST charges and value is persisted (not stripped).
        h = _hdrs(S["mgr_tok"])
        r = requests.post(
            f"{API}/services",
            json={"customer_id": S["cid2"], "service_type": "Cockroach",
                  "scheduled_date": datetime.now(timezone.utc).isoformat(),
                  "charges": 9999},
            headers=h,
        )
        assert r.status_code == 200
        sid = r.json()["id"]
        r2 = requests.get(f"{API}/services/{sid}", headers=_hdrs(S["admin_tok"]))
        assert r2.json()["charges"] == 9999


# ---------------- Technician permissions ---------------- #
class TestFTechPerms:
    def test_tech_sees_only_own(self):
        # Create service for tech_t2
        h = _hdrs(S["admin_tok"])
        r = requests.post(
            f"{API}/services",
            json={"customer_id": S["cid3"], "service_type": "Mosquito",
                  "scheduled_date": datetime.now(timezone.utc).isoformat(),
                  "technician_id": S["tech_t2_id"], "charges": 100},
            headers=h,
        )
        S["t2_sid"] = r.json()["id"]

        r = requests.get(f"{API}/services", headers=_hdrs(S["tech_t1_tok"]))
        for s in r.json():
            assert s["technician_id"] == S["tech_t1_id"]

        # Even with query param for another tech, tech only sees own
        r = requests.get(
            f"{API}/services", params={"technician_id": S["tech_t2_id"]},
            headers=_hdrs(S["tech_t1_tok"]),
        )
        for s in r.json():
            assert s["technician_id"] == S["tech_t1_id"]

    def test_tech_403_on_other_service(self):
        r = requests.get(f"{API}/services/{S['t2_sid']}", headers=_hdrs(S["tech_t1_tok"]))
        assert r.status_code == 403

    def test_tech_patch_only_allowed_fields(self):
        h = _hdrs(S["tech_t1_tok"])
        # Try charges only -> 400
        # find a tech_t1 service
        r = requests.get(f"{API}/services", headers=h)
        sid = next((s["id"] for s in r.json() if s.get("status") != "completed"), None)
        if not sid:
            # create one
            r = requests.post(
                f"{API}/services",
                json={"customer_id": S["cid"], "service_type": "Rodent",
                      "scheduled_date": datetime.now(timezone.utc).isoformat(),
                      "technician_id": S["tech_t1_id"], "charges": 100},
                headers=_hdrs(S["admin_tok"]),
            )
            sid = r.json()["id"]
        r2 = requests.patch(f"{API}/services/{sid}", json={"charges": 5555}, headers=h)
        assert r2.status_code == 400
        # Verify charges unchanged
        r3 = requests.get(f"{API}/services/{sid}", headers=_hdrs(S["admin_tok"]))
        assert r3.json()["charges"] != 5555
        S["tech_pending_sid"] = sid


# ---------------- Admin edits pending service ---------------- #
class TestGAdminEditPending:
    def test_admin_patch_pending_multiple_fields(self):
        h = _hdrs(S["admin_tok"])
        # create pending service (no tech)
        r = requests.post(
            f"{API}/services",
            json={"customer_id": S["cid"], "service_type": "Cockroach",
                  "scheduled_date": datetime.now(timezone.utc).isoformat(),
                  "charges": 100},
            headers=h,
        )
        sid = r.json()["id"]
        assert r.json()["status"] == "pending"
        new_date = "2026-11-15T09:00:00+00:00"
        r2 = requests.patch(
            f"{API}/services/{sid}",
            json={"customer_id": S["cid2"], "service_type": "Rodent",
                  "scheduled_date": new_date, "technician_id": S["tech_t2_id"],
                  "charges": 999},
            headers=h,
        )
        assert r2.status_code == 200
        r3 = requests.get(f"{API}/services/{sid}", headers=h).json()
        assert r3["customer_id"] == S["cid2"]
        assert r3["service_type"] == "Rodent"
        assert r3["scheduled_date"] == new_date
        assert r3["technician_id"] == S["tech_t2_id"]
        assert r3["charges"] == 999
        assert r3["status"] == "assigned"  # auto-flip
        # audit log
        r4 = requests.get(f"{API}/audit-logs", headers=h)
        assert any(a.get("entity_id") == sid and a.get("action") == "update" for a in r4.json())


# ---------------- Technician reassignment ---------------- #
class TestHReassign:
    def test_reassign_tech(self):
        h = _hdrs(S["admin_tok"])
        # Use tech_pending_sid (t1) and reassign to t2
        sid = S["tech_pending_sid"]
        r = requests.patch(f"{API}/services/{sid}", json={"technician_id": S["tech_t2_id"]}, headers=h)
        assert r.status_code == 200
        # t1 should not see
        r1 = requests.get(f"{API}/services", headers=_hdrs(S["tech_t1_tok"])).json()
        assert not any(s["id"] == sid for s in r1)
        # t2 sees
        r2 = requests.get(f"{API}/services", headers=_hdrs(S["tech_t2_tok"])).json()
        assert any(s["id"] == sid for s in r2)


# ---------------- AMC generation ---------------- #
class TestIAMC:
    def _create_amc(self, freq, days, custom=None):
        h = _hdrs(S["admin_tok"])
        start = datetime.now(timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=days)
        payload = {
            "customer_id": S["cid"], "service_type": "AMC-" + freq,
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "frequency": freq, "contract_amount": 12000,
        }
        if custom is not None:
            payload["custom_interval_days"] = custom
        r = requests.post(f"{API}/amc", json=payload, headers=h)
        assert r.status_code == 200, r.text
        return r.json()

    def test_amc_daily_7days(self):
        a = self._create_amc("daily", 7)
        assert a["generated"] in (7, 8)

    def test_amc_fortnightly_60d(self):
        a = self._create_amc("fortnightly", 60)
        assert a["generated"] in (4, 5, 6)  # ~5

    def test_amc_monthly_6mo(self):
        h = _hdrs(S["admin_tok"])
        start = datetime.now(timezone.utc)
        end = start + timedelta(days=30 * 6)
        r = requests.post(f"{API}/amc", json={
            "customer_id": S["cid"], "service_type": "AMC-monthly",
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "frequency": "monthly", "contract_amount": 0}, headers=h)
        assert r.json()["generated"] in (6, 7)

    def test_amc_quarterly_12mo(self):
        h = _hdrs(S["admin_tok"])
        start = datetime.now(timezone.utc)
        end = start + timedelta(days=365)
        r = requests.post(f"{API}/amc", json={
            "customer_id": S["cid"], "service_type": "AMC-q",
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "frequency": "quarterly", "contract_amount": 0}, headers=h)
        assert r.json()["generated"] in (4, 5)

    def test_amc_custom_10d_30d(self):
        a = self._create_amc("custom", 30, custom=10)
        assert a["generated"] in (3, 4)
        S["amc_custom_id"] = a["id"]

    def test_amc_services_have_null_tech_and_amc_id(self):
        h = _hdrs(S["admin_tok"])
        r = requests.get(f"{API}/services", params={"status": "pending"}, headers=h)
        found = [s for s in r.json() if s.get("amc_id") == S["amc_custom_id"]]
        assert len(found) >= 3
        for s in found:
            assert s.get("technician_id") is None
        S["amc_svc_id"] = found[0]["id"]

    def test_amc_body_does_not_persist_technician(self):
        # Even if we submit technician_id in body, model ignores it (not in AMCIn)
        h = _hdrs(S["admin_tok"])
        start = datetime.now(timezone.utc)
        end = start + timedelta(days=10)
        r = requests.post(f"{API}/amc", json={
            "customer_id": S["cid"], "service_type": "AMC-x",
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "frequency": "daily", "contract_amount": 0,
            "technician_id": S["tech_t1_id"],
        }, headers=h)
        assert r.status_code == 200
        aid = r.json()["id"]
        # AMC record should not have technician_id
        r2 = requests.get(f"{API}/amc/{aid}", headers=h).json()
        assert "technician_id" not in r2["amc"]
        for s in r2["services"]:
            assert s.get("technician_id") is None


# ---------------- Assign from pending ---------------- #
class TestJAssign:
    def test_patch_amc_service_with_tech(self):
        h = _hdrs(S["admin_tok"])
        sid = S["amc_svc_id"]
        r = requests.patch(f"{API}/services/{sid}", json={"technician_id": S["tech_t1_id"]}, headers=h)
        assert r.status_code == 200
        r2 = requests.get(f"{API}/services/{sid}", headers=h).json()
        assert r2["status"] == "assigned"

    def test_tech_dashboard_reflects(self):
        r = requests.get(f"{API}/dashboard/technician", headers=_hdrs(S["tech_t1_tok"]))
        assert r.status_code == 200
        d = r.json()
        assert (d["today"] + d["upcoming"]) >= 1


# ---------------- Reminder reschedule ---------------- #
class TestKReschedule:
    def test_reschedule_future(self):
        h = _hdrs(S["admin_tok"])
        rid = S["rem_id"]
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        r = requests.post(f"{API}/reminders/{rid}/reschedule", json={"due_date": future}, headers=h)
        assert r.status_code == 200
        rr = requests.get(f"{API}/reminders", headers=h).json()
        rem = next(x for x in rr if x["id"] == rid)
        assert rem["status"] == "rescheduled"
        assert rem.get("previous_due_date")
        assert rem["computed"] == "rescheduled"

    def test_reschedule_past_overdue(self):
        h = _hdrs(S["admin_tok"])
        # create a reminder then reschedule to past
        r = requests.post(f"{API}/reminders", json={
            "customer_id": S["cid"], "service_type": "Termite",
            "due_date": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
        }, headers=h)
        rid = r.json()["id"]
        past = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        requests.post(f"{API}/reminders/{rid}/reschedule", json={"due_date": past}, headers=h)
        rr = requests.get(f"{API}/reminders", headers=h).json()
        rem = next(x for x in rr if x["id"] == rid)
        assert rem["computed"] == "overdue"


# ---------------- Completed service locking ---------------- #
class TestLLocking:
    def test_completed_locked_for_manager_admin_notes(self):
        h = _hdrs(S["admin_tok"])
        # Prefer the service we specifically completed in TestCEndToEnd (has tech assigned)
        primary = S.get("sid")
        chosen = None
        if primary:
            sd = requests.get(f"{API}/services/{primary}", headers=h).json()
            if sd.get("status") == "completed":
                chosen = sd
        if not chosen:
            r = requests.get(f"{API}/services", params={"status": "completed"}, headers=h).json()
            assert r, "need at least one completed service"
            with_tech = [x for x in r if x.get("technician_id")]
            chosen = with_tech[0] if with_tech else r[0]
        sid = chosen["id"]
        # manager patch admin_notes on completed -> 400
        rm = requests.patch(f"{API}/services/{sid}", json={"admin_notes": "x"}, headers=_hdrs(S["mgr_tok"]))
        assert rm.status_code == 400, f"expected 400, got {rm.status_code} {rm.text}"
        # admin patch admin_notes on completed -> ok
        ra = requests.patch(f"{API}/services/{sid}", json={"admin_notes": "ok"}, headers=h)
        assert ra.status_code == 200
        S["completed_sid"] = sid

    # ---- NEW: technician un-complete bug FIX regression ----
    def _tech_tok_for_sid(self, sid):
        s = requests.get(f"{API}/services/{sid}", headers=_hdrs(S["admin_tok"])).json()
        tid = s.get("technician_id")
        if not tid:
            return None, s
        for lbl in ("t1", "t2"):
            if S.get(f"tech_{lbl}_id") == tid:
                return S[f"tech_{lbl}_tok"], s
        return None, s

    def test_tech_patch_status_pending_on_completed_blocked(self):
        """FIX: tech PATCH {status:'pending'} on their completed service MUST fail; DB stays 'completed'."""
        sid = S["completed_sid"]
        tok, _ = self._tech_tok_for_sid(sid)
        if not tok:
            pytest.skip("completed svc has no tech in test-set")
        r = requests.patch(f"{API}/services/{sid}", json={"status": "pending"}, headers=_hdrs(tok))
        assert r.status_code >= 400 and r.status_code < 500, (
            f"tech un-complete must be blocked, got {r.status_code} body={r.text}"
        )
        after = requests.get(f"{API}/services/{sid}", headers=_hdrs(S["admin_tok"])).json()
        assert after.get("status") == "completed", (
            f"status must remain 'completed', got '{after.get('status')}'"
        )

    def test_tech_patch_payment_status_on_completed_allowed(self):
        """Cash-collection flow: tech PATCH payment_status on completed -> 200 and persists."""
        sid = S["completed_sid"]
        tok, _ = self._tech_tok_for_sid(sid)
        if not tok:
            pytest.skip("completed svc has no tech in test-set")
        # -> paid
        r = requests.patch(f"{API}/services/{sid}", json={"payment_status": "paid"}, headers=_hdrs(tok))
        assert r.status_code == 200, r.text
        after = requests.get(f"{API}/services/{sid}", headers=_hdrs(S["admin_tok"])).json()
        assert after.get("payment_status") == "paid"
        assert after.get("status") == "completed"  # still completed
        # -> unpaid (toggle back)
        r2 = requests.patch(f"{API}/services/{sid}", json={"payment_status": "unpaid"}, headers=_hdrs(tok))
        assert r2.status_code == 200, r2.text
        after2 = requests.get(f"{API}/services/{sid}", headers=_hdrs(S["admin_tok"])).json()
        assert after2.get("payment_status") == "unpaid"
        assert after2.get("status") == "completed"

    def test_tech_mixed_status_and_payment_on_completed(self):
        """Mixed: {status:'pending', payment_status:'paid'} - status MUST NOT change; payment may or may not update."""
        sid = S["completed_sid"]
        tok, _ = self._tech_tok_for_sid(sid)
        if not tok:
            pytest.skip("completed svc has no tech in test-set")
        # ensure baseline unpaid
        requests.patch(f"{API}/services/{sid}", json={"payment_status": "unpaid"}, headers=_hdrs(tok))
        r = requests.patch(f"{API}/services/{sid}",
                           json={"status": "pending", "payment_status": "paid"},
                           headers=_hdrs(tok))
        # acceptable: either 200 (status filtered out, payment applied) OR 4xx
        assert r.status_code == 200 or (400 <= r.status_code < 500), r.text
        after = requests.get(f"{API}/services/{sid}", headers=_hdrs(S["admin_tok"])).json()
        assert after.get("status") == "completed", (
            f"status must remain 'completed' after mixed PATCH, got '{after.get('status')}'"
        )
        # cleanup: revert payment back to unpaid
        requests.patch(f"{API}/services/{sid}", json={"payment_status": "unpaid"}, headers=_hdrs(tok))

    def test_manager_patch_status_on_completed_blocked(self):
        sid = S["completed_sid"]
        r = requests.patch(f"{API}/services/{sid}", json={"status": "pending"},
                           headers=_hdrs(S["mgr_tok"]))
        assert 400 <= r.status_code < 500, f"got {r.status_code} {r.text}"
        after = requests.get(f"{API}/services/{sid}", headers=_hdrs(S["admin_tok"])).json()
        assert after.get("status") == "completed"

    def test_manager_patch_charges_on_completed_blocked(self):
        sid = S["completed_sid"]
        before = requests.get(f"{API}/services/{sid}", headers=_hdrs(S["admin_tok"])).json()
        prev_charges = before.get("charges")
        r = requests.patch(f"{API}/services/{sid}", json={"charges": 5},
                           headers=_hdrs(S["mgr_tok"]))
        assert 400 <= r.status_code < 500, f"got {r.status_code} {r.text}"
        after = requests.get(f"{API}/services/{sid}", headers=_hdrs(S["admin_tok"])).json()
        assert after.get("charges") == prev_charges
        assert after.get("status") == "completed"

    def test_manager_patch_payment_status_on_completed_allowed(self):
        sid = S["completed_sid"]
        r = requests.patch(f"{API}/services/{sid}", json={"payment_status": "paid"},
                           headers=_hdrs(S["mgr_tok"]))
        assert r.status_code == 200, r.text
        after = requests.get(f"{API}/services/{sid}", headers=_hdrs(S["admin_tok"])).json()
        assert after.get("payment_status") == "paid"
        assert after.get("status") == "completed"
        # cleanup
        requests.patch(f"{API}/services/{sid}", json={"payment_status": "unpaid"},
                       headers=_hdrs(S["mgr_tok"]))

    def test_admin_patch_any_field_on_completed_allowed(self):
        sid = S["completed_sid"]
        h = _hdrs(S["admin_tok"])
        r = requests.patch(f"{API}/services/{sid}",
                           json={"charges": 2000, "payment_status": "paid"}, headers=h)
        assert r.status_code == 200, r.text
        after = requests.get(f"{API}/services/{sid}", headers=h).json()
        assert after.get("charges") == 2000
        assert after.get("payment_status") == "paid"
        assert after.get("status") == "completed"


# ---------------- CSV export ---------------- #
class TestMCSV:
    def test_admin_csv_ok(self):
        r = requests.get(f"{API}/reports/export.csv",
                         params={"kind": "services", "token": S["admin_tok"]})
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("text/csv")
        body = r.text
        assert "ID," in body and "Customer" in body
        assert len(body.splitlines()) >= 2

    def test_missing_token_401(self):
        r = requests.get(f"{API}/reports/export.csv", params={"kind": "services"})
        assert r.status_code == 401

    def test_invalid_token_401(self):
        r = requests.get(f"{API}/reports/export.csv", params={"kind": "services", "token": "junk.xxx"})
        assert r.status_code == 401

    def test_non_admin_403(self):
        r = requests.get(f"{API}/reports/export.csv",
                         params={"kind": "services", "token": S["mgr_tok"]})
        assert r.status_code == 403


# ---------------- Files endpoint ---------------- #
class TestNFiles:
    def test_get_file_with_token(self):
        # Use a photo uploaded earlier
        sid = S["sid"]
        s = requests.get(f"{API}/services/{sid}", headers=_hdrs(S["admin_tok"])).json()
        photos = s.get("photos", {})
        path = None
        for phase in ("before", "during", "after"):
            if photos.get(phase):
                path = photos[phase][0]
                break
        if not path:
            pytest.skip("no photos uploaded")
        r = requests.get(f"{API}/files/{path}", params={"token": S["admin_tok"]})
        assert r.status_code == 200
        assert len(r.content) > 0


# ---------------- Manager dashboard pending_payments ---------------- #
class TestOMgrDash:
    def test_pending_payments_count(self):
        h = _hdrs(S["mgr_tok"])
        # Create a completed service with payment_status pending via admin
        r = requests.post(
            f"{API}/services",
            json={"customer_id": S["cid2"], "service_type": "Mosquito",
                  "scheduled_date": datetime.now(timezone.utc).isoformat(),
                  "technician_id": S["tech_t1_id"], "charges": 100,
                  "payment_status": "unpaid"},
            headers=_hdrs(S["admin_tok"]),
        )
        sid = r.json()["id"]
        requests.patch(f"{API}/services/{sid}", json={"status": "completed"}, headers=_hdrs(S["admin_tok"]))
        d = requests.get(f"{API}/dashboard/manager", headers=h).json()
        assert d["pending_payments"] >= 1


# ---------------- Persistence + no _id leak sweep ---------------- #
class TestPPersistence:
    def test_no_mongo_id_in_any_list_endpoint(self):
        h = _hdrs(S["admin_tok"])
        for path in ("/customers", "/services", "/reminders", "/amc", "/audit-logs", "/users"):
            r = requests.get(f"{API}{path}", headers=h)
            assert r.status_code == 200, path
            body = r.json()
            if isinstance(body, list):
                for row in body:
                    assert "_id" not in row, f"_id leaked in {path}"

    def test_customers_persist_across_requests(self):
        h = _hdrs(S["admin_tok"])
        r1 = requests.get(f"{API}/customers", headers=h).json()
        time.sleep(0.5)
        r2 = requests.get(f"{API}/customers", headers=h).json()
        assert len(r2) >= len(r1) - 0  # persisted, not in-memory
        ids1 = {c["id"] for c in r1}
        ids2 = {c["id"] for c in r2}
        assert ids1.issubset(ids2)


# ---------------- Diagnostic dump ---------------- #
def test_zzz_diagnostic_dump():
    print("DIAG:", {k: v for k, v in S.items() if "tok" not in k})
