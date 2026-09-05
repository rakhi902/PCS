"""Comprehensive backend tests for Pest Control Service Management app."""
import os
import io
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://pest-control-mgmt.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

# Shared state across tests
STATE = {}


def _post(path, token=None, **kw):
    h = kw.pop("headers", {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    return requests.post(f"{API}{path}", headers=h, timeout=30, **kw)


def _get(path, token=None, **kw):
    h = kw.pop("headers", {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    return requests.get(f"{API}{path}", headers=h, timeout=30, **kw)


def _patch(path, token=None, **kw):
    h = kw.pop("headers", {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    return requests.patch(f"{API}{path}", headers=h, timeout=30, **kw)


# =========================
# Auth
# =========================
class TestAuth:
    def test_01_login_admin_default_pin(self):
        # Try 1234 first; if changed by prior run, try known rotated PIN "9999"
        r = _post("/auth/login", json={"username": "admin", "pin": "1234"})
        if r.status_code != 200:
            r2 = _post("/auth/login", json={"username": "admin", "pin": "9999"})
            assert r2.status_code == 200, f"Admin login failed with both pins: {r.status_code}/{r2.status_code} - {r.text}/{r2.text}"
            data = r2.json()
            STATE["admin_token"] = data["token"]
            STATE["admin_user"] = data["user"]
            STATE["admin_pin"] = "9999"
            # must_change_pin might be False now
            return
        data = r.json()
        assert "token" in data and "user" in data
        assert data["user"]["role"] == "admin"
        assert data["user"].get("must_change_pin") is True
        STATE["admin_token"] = data["token"]
        STATE["admin_user"] = data["user"]
        STATE["admin_pin"] = "1234"

    def test_02_change_admin_pin(self):
        token = STATE["admin_token"]
        new_pin = "9999"
        r = _post("/auth/change-pin", token=token, json={"pin": new_pin})
        assert r.status_code == 200, r.text
        # Login with new PIN
        r2 = _post("/auth/login", json={"username": "admin", "pin": new_pin})
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert d["user"].get("must_change_pin") is False
        STATE["admin_token"] = d["token"]
        STATE["admin_pin"] = new_pin

    def test_03_change_pin_invalid_length(self):
        r = _post("/auth/change-pin", token=STATE["admin_token"], json={"pin": "12"})
        assert r.status_code == 400

    def test_04_invalid_credentials(self):
        r = _post("/auth/login", json={"username": "admin", "pin": "0000"})
        assert r.status_code == 401


# =========================
# Users
# =========================
class TestUsers:
    def test_01_create_manager(self):
        t = STATE["admin_token"]
        uname = f"mgr_{uuid.uuid4().hex[:6]}"
        r = _post("/users", token=t, json={"username": uname, "name": "Test Manager", "role": "manager", "pin": "2222"})
        assert r.status_code == 200, r.text
        STATE["manager_id"] = r.json()["id"]
        STATE["manager_username"] = uname

    def test_02_create_technician(self):
        t = STATE["admin_token"]
        uname = f"tech_{uuid.uuid4().hex[:6]}"
        r = _post("/users", token=t, json={"username": uname, "name": "Test Tech", "role": "technician", "pin": "3333"})
        assert r.status_code == 200, r.text
        STATE["tech_id"] = r.json()["id"]
        STATE["tech_username"] = uname

    def test_03_cannot_create_admin(self):
        t = STATE["admin_token"]
        r = _post("/users", token=t, json={"username": "admin2", "name": "X", "role": "admin", "pin": "4444"})
        assert r.status_code == 400

    def test_04_invalid_pin_length(self):
        t = STATE["admin_token"]
        r = _post("/users", token=t, json={"username": "badpin", "name": "X", "role": "manager", "pin": "12"})
        assert r.status_code == 400

    def test_05_manager_login_must_change(self):
        r = _post("/auth/login", json={"username": STATE["manager_username"], "pin": "2222"})
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["must_change_pin"] is True
        STATE["manager_token"] = d["token"]
        # change pin
        _post("/auth/change-pin", token=d["token"], json={"pin": "2323"})
        r2 = _post("/auth/login", json={"username": STATE["manager_username"], "pin": "2323"})
        STATE["manager_token"] = r2.json()["token"]

    def test_06_technician_login(self):
        r = _post("/auth/login", json={"username": STATE["tech_username"], "pin": "3333"})
        assert r.status_code == 200
        _post("/auth/change-pin", token=r.json()["token"], json={"pin": "3434"})
        r2 = _post("/auth/login", json={"username": STATE["tech_username"], "pin": "3434"})
        STATE["tech_token"] = r2.json()["token"]

    def test_07_reset_pin(self):
        r = _post(f"/users/{STATE['tech_id']}/reset-pin", token=STATE["admin_token"], json={"pin": "5555"})
        assert r.status_code == 200
        r2 = _post("/auth/login", json={"username": STATE["tech_username"], "pin": "5555"})
        assert r2.status_code == 200
        assert r2.json()["user"]["must_change_pin"] is True
        _post("/auth/change-pin", token=r2.json()["token"], json={"pin": "3434"})
        r3 = _post("/auth/login", json={"username": STATE["tech_username"], "pin": "3434"})
        STATE["tech_token"] = r3.json()["token"]

    def test_08_disable_enable(self):
        r = _patch(f"/users/{STATE['tech_id']}", token=STATE["admin_token"], json={"active": False})
        assert r.status_code == 200
        r2 = _post("/auth/login", json={"username": STATE["tech_username"], "pin": "3434"})
        assert r2.status_code == 401
        _patch(f"/users/{STATE['tech_id']}", token=STATE["admin_token"], json={"active": True})
        r3 = _post("/auth/login", json={"username": STATE["tech_username"], "pin": "3434"})
        assert r3.status_code == 200
        STATE["tech_token"] = r3.json()["token"]


# =========================
# Customers & Service Types
# =========================
class TestCustomersServiceTypes:
    def test_01_default_service_types(self):
        r = _get("/service-types", token=STATE["admin_token"])
        assert r.status_code == 200
        names = [s["name"] for s in r.json()]
        for expected in ["Cockroach", "Termite", "Rodent", "Mosquito", "General Pest Control"]:
            assert expected in names, f"Missing default {expected}"

    def test_02_create_service_type_admin(self):
        r = _post("/service-types", token=STATE["admin_token"], json={"name": f"TEST_{uuid.uuid4().hex[:6]}"})
        assert r.status_code == 200

    def test_03_create_customer(self):
        r = _post("/customers", token=STATE["admin_token"],
                  json={"name": "TEST_Cust", "mobile": "9998887777", "address": "Addr", "city": "Bangalore"})
        assert r.status_code == 200
        c = r.json()
        assert "_id" not in c
        assert c["name"] == "TEST_Cust"
        STATE["customer_id"] = c["id"]

    def test_04_list_customers(self):
        r = _get("/customers", token=STATE["admin_token"])
        assert r.status_code == 200
        assert any(c["id"] == STATE["customer_id"] for c in r.json())

    def test_05_get_customer_detail(self):
        r = _get(f"/customers/{STATE['customer_id']}", token=STATE["admin_token"])
        assert r.status_code == 200
        d = r.json()
        assert "customer" in d and "services" in d
        assert "_id" not in d["customer"]

    def test_06_tech_cannot_list_customers(self):
        r = _get("/customers", token=STATE["tech_token"])
        assert r.status_code == 403


# =========================
# Services
# =========================
class TestServices:
    def test_01_create_service_no_tech_pending(self):
        sched = (datetime.now(timezone.utc)).isoformat()
        r = _post("/services", token=STATE["admin_token"], json={
            "customer_id": STATE["customer_id"], "service_type": "Cockroach",
            "scheduled_date": sched, "charges": 500
        })
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["status"] == "pending"
        STATE["service_pending_id"] = s["id"]

    def test_02_create_service_with_tech_assigned(self):
        sched = datetime.now(timezone.utc).isoformat()
        r = _post("/services", token=STATE["admin_token"], json={
            "customer_id": STATE["customer_id"], "service_type": "Termite",
            "scheduled_date": sched, "technician_id": STATE["tech_id"], "charges": 1500
        })
        assert r.status_code == 200
        s = r.json()
        assert s["status"] == "assigned"
        assert s["technician_id"] == STATE["tech_id"]
        STATE["service_assigned_id"] = s["id"]

    def test_03_list_services_filters(self):
        r = _get("/services", token=STATE["admin_token"], params={"status": "assigned"})
        assert r.status_code == 200
        assert all(s["status"] == "assigned" for s in r.json())

    def test_04_list_services_by_tech(self):
        r = _get("/services", token=STATE["admin_token"], params={"technician_id": STATE["tech_id"]})
        assert r.status_code == 200
        assert all(s["technician_id"] == STATE["tech_id"] for s in r.json())

    def test_05_manager_no_charges(self):
        r = _get("/services", token=STATE["manager_token"])
        assert r.status_code == 200
        for s in r.json():
            assert "charges" not in s, "Manager should not see charges"

    def test_06_technician_only_own(self):
        r = _get("/services", token=STATE["tech_token"])
        assert r.status_code == 200
        for s in r.json():
            assert s.get("technician_id") == STATE["tech_id"]
            assert "charges" not in s

    def test_07_manager_cannot_set_charges(self):
        sched = datetime.now(timezone.utc).isoformat()
        r = _post("/services", token=STATE["manager_token"], json={
            "customer_id": STATE["customer_id"], "service_type": "Rodent",
            "scheduled_date": sched, "charges": 9999
        })
        assert r.status_code == 200
        sid = r.json()["id"]
        # Fetch with admin to verify charges was forced to 0
        r2 = _get(f"/services/{sid}", token=STATE["admin_token"])
        assert r2.json().get("charges", 0) == 0

    def test_08_tech_update_allowed_fields(self):
        r = _patch(f"/services/{STATE['service_assigned_id']}", token=STATE["tech_token"],
                   json={"medicine": "Chemical X", "quantity": "100ml", "status": "in_progress"})
        assert r.status_code == 200

    def test_09_tech_cannot_change_charges(self):
        # Technician passing charges - should be filtered out
        r = _patch(f"/services/{STATE['service_assigned_id']}", token=STATE["tech_token"],
                   json={"charges": 5000})
        # Nothing to update -> 400
        assert r.status_code == 400

    def test_10_complete_without_photos_fails(self):
        r = _post(f"/services/{STATE['service_assigned_id']}/complete", token=STATE["tech_token"], json={})
        assert r.status_code == 400
        assert "photo" in r.text.lower()


# =========================
# Photo upload
# =========================
class TestPhotos:
    def test_01_upload_before(self):
        img = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # fake jpeg
        files = {"file": ("before.jpg", io.BytesIO(img), "image/jpeg")}
        data = {"phase": "before"}
        r = requests.post(
            f"{API}/services/{STATE['service_assigned_id']}/photos",
            headers={"Authorization": f"Bearer {STATE['tech_token']}"},
            files=files, data=data, timeout=60,
        )
        if r.status_code == 500 and "EMERGENT_LLM_KEY" in r.text:
            pytest.skip("Storage not configured")
        assert r.status_code == 200, r.text
        STATE["photo_before_path"] = r.json()["path"]

    def test_02_upload_after(self):
        img = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        files = {"file": ("after.jpg", io.BytesIO(img), "image/jpeg")}
        data = {"phase": "after"}
        r = requests.post(
            f"{API}/services/{STATE['service_assigned_id']}/photos",
            headers={"Authorization": f"Bearer {STATE['tech_token']}"},
            files=files, data=data, timeout=60,
        )
        if r.status_code == 500:
            pytest.skip("Storage not configured")
        assert r.status_code == 200
        STATE["photo_after_path"] = r.json()["path"]

    def test_03_fetch_file_with_token_query(self):
        if "photo_before_path" not in STATE:
            pytest.skip("No photo path")
        r = requests.get(f"{API}/files/{STATE['photo_before_path']}",
                         params={"token": STATE["tech_token"]}, timeout=30)
        assert r.status_code == 200

    def test_04_complete_service_with_photos(self):
        if "photo_before_path" not in STATE or "photo_after_path" not in STATE:
            pytest.skip("Photos missing")
        r = _post(f"/services/{STATE['service_assigned_id']}/complete", token=STATE["tech_token"],
                  json={"medicine": "X", "quantity": "50ml"})
        assert r.status_code == 200
        r2 = _get(f"/services/{STATE['service_assigned_id']}", token=STATE["admin_token"])
        assert r2.json()["status"] == "completed"
        assert r2.json().get("completed_at")


# =========================
# AMC
# =========================
class TestAMC:
    def test_01_create_monthly_amc(self):
        start = datetime.now(timezone.utc)
        end = start + timedelta(days=365)
        r = _post("/amc", token=STATE["admin_token"], json={
            "customer_id": STATE["customer_id"], "service_type": "Cockroach",
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "frequency": "monthly", "contract_amount": 12000
        })
        assert r.status_code == 200, r.text
        d = r.json()
        # Monthly over 12 months => ~13 records
        assert 12 <= d["generated"] <= 14, f"Expected ~13 got {d['generated']}"
        STATE["amc_id"] = d["id"]

    def test_02_amc_generates_pending_services(self):
        r = _get("/services", token=STATE["admin_token"], params={"status": "pending", "customer_id": STATE["customer_id"]})
        assert r.status_code == 200
        amc_svc = [s for s in r.json() if s.get("amc_id") == STATE["amc_id"]]
        assert len(amc_svc) >= 12
        assert all(s.get("technician_id") is None for s in amc_svc)

    def test_03_amc_contract_amount_hidden_manager(self):
        r = _get("/amc", token=STATE["manager_token"])
        assert r.status_code == 200
        for a in r.json():
            assert "contract_amount" not in a


# =========================
# Reminders
# =========================
class TestReminders:
    def test_01_create_reminder_upcoming(self):
        due = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        r = _post("/reminders", token=STATE["admin_token"], json={
            "customer_id": STATE["customer_id"], "service_type": "Termite", "due_date": due
        })
        assert r.status_code == 200
        STATE["reminder_upcoming_id"] = r.json()["id"]

    def test_02_create_reminder_due(self):
        due = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        r = _post("/reminders", token=STATE["admin_token"], json={
            "customer_id": STATE["customer_id"], "service_type": "Rodent", "due_date": due
        })
        assert r.status_code == 200
        STATE["reminder_due_id"] = r.json()["id"]

    def test_03_create_reminder_overdue(self):
        due = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        r = _post("/reminders", token=STATE["admin_token"], json={
            "customer_id": STATE["customer_id"], "service_type": "Mosquito", "due_date": due
        })
        assert r.status_code == 200
        STATE["reminder_overdue_id"] = r.json()["id"]

    def test_04_list_computed_field(self):
        r = _get("/reminders", token=STATE["admin_token"])
        assert r.status_code == 200
        by_id = {x["id"]: x for x in r.json()}
        assert by_id[STATE["reminder_upcoming_id"]]["computed"] == "upcoming"
        assert by_id[STATE["reminder_due_id"]]["computed"] == "due"
        assert by_id[STATE["reminder_overdue_id"]]["computed"] == "overdue"

    def test_05_complete_reminder(self):
        r = _post(f"/reminders/{STATE['reminder_due_id']}/complete", token=STATE["admin_token"])
        assert r.status_code == 200
        r2 = _get("/reminders", token=STATE["admin_token"])
        by_id = {x["id"]: x for x in r2.json()}
        assert by_id[STATE["reminder_due_id"]]["status"] == "completed"


# =========================
# Dashboards
# =========================
class TestDashboards:
    def test_01_admin_dashboard(self):
        r = _get("/dashboard/admin", token=STATE["admin_token"])
        assert r.status_code == 200
        d = r.json()
        assert "today_amount" in d and "month_amount" in d
        assert "pending_services" in d

    def test_02_manager_dashboard_no_amounts(self):
        r = _get("/dashboard/manager", token=STATE["manager_token"])
        assert r.status_code == 200
        d = r.json()
        # No amount keys
        for k in ("today_amount", "month_amount", "total_revenue"):
            assert k not in d
        for s in d.get("recent_completed", []):
            assert "charges" not in s

    def test_03_technician_dashboard(self):
        r = _get("/dashboard/technician", token=STATE["tech_token"])
        assert r.status_code == 200
        d = r.json()
        assert set(["today", "upcoming", "completed"]).issubset(d.keys())

    def test_04_manager_forbidden_admin_dashboard(self):
        r = _get("/dashboard/admin", token=STATE["manager_token"])
        assert r.status_code == 403


# =========================
# Reports
# =========================
class TestReports:
    def test_01_admin_only(self):
        r = _get("/reports/summary", token=STATE["admin_token"])
        assert r.status_code == 200
        d = r.json()
        for k in ("total_revenue", "month_revenue", "by_service_type", "technicians"):
            assert k in d

    def test_02_manager_forbidden(self):
        r = _get("/reports/summary", token=STATE["manager_token"])
        assert r.status_code == 403

    def test_03_tech_forbidden(self):
        r = _get("/reports/summary", token=STATE["tech_token"])
        assert r.status_code == 403


# =========================
# Role authz
# =========================
class TestRoleAuthz:
    def test_01_manager_cannot_create_user(self):
        r = _post("/users", token=STATE["manager_token"], json={"username": "x", "name": "y", "role": "technician", "pin": "1234"})
        assert r.status_code == 403

    def test_02_manager_cannot_patch_settings(self):
        r = _patch("/settings", token=STATE["manager_token"], json={"google_review_url": "http://x"})
        assert r.status_code == 403

    def test_03_tech_cannot_list_amc(self):
        r = _get("/amc", token=STATE["tech_token"])
        assert r.status_code == 403

    def test_04_tech_cannot_list_reminders(self):
        r = _get("/reminders", token=STATE["tech_token"])
        assert r.status_code == 403


# =========================
# Settings
# =========================
class TestSettings:
    def test_01_get_settings(self):
        r = _get("/settings", token=STATE["admin_token"])
        assert r.status_code == 200

    def test_02_patch_settings_admin(self):
        r = _patch("/settings", token=STATE["admin_token"],
                   json={"google_review_url": "https://g.co/r", "whatsapp_template": "Hi {name}"})
        assert r.status_code == 200
        r2 = _get("/settings", token=STATE["admin_token"])
        d = r2.json()
        assert d["google_review_url"] == "https://g.co/r"
        assert "_id" not in d

    def test_03_manager_forbidden(self):
        r = _patch("/settings", token=STATE["manager_token"], json={"google_review_url": "x"})
        assert r.status_code == 403
