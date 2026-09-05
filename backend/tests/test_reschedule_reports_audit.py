"""Backend tests for newly added features:
- Reminder reschedule endpoint + PATCH reminder auto-reschedule
- /reports/summary extra fields (admin only)
- /audit-logs admin-only + reschedule creates audit entry
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

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


def _admin_login():
    for pin in ("1234", "9999"):
        r = _post("/auth/login", json={"username": "admin", "pin": pin})
        if r.status_code == 200:
            data = r.json()
            token = data["token"]
            if data["user"].get("must_change_pin"):
                # rotate to 9999 if still on 1234
                _post("/auth/change-pin", token=token, json={"pin": "9999"})
                r2 = _post("/auth/login", json={"username": "admin", "pin": "9999"})
                return r2.json()["token"]
            return token
    raise AssertionError("Admin login failed with both 1234 and 9999")


@pytest.fixture(scope="module", autouse=True)
def setup_context():
    """Create admin, manager, technician tokens + a test customer for the module."""
    admin_token = _admin_login()
    STATE["admin_token"] = admin_token

    # Manager
    mgr_uname = f"tmgr_{uuid.uuid4().hex[:6]}"
    r = _post("/users", token=admin_token,
              json={"username": mgr_uname, "name": "TEST_Manager", "role": "manager", "pin": "2222"})
    assert r.status_code == 200, r.text
    r2 = _post("/auth/login", json={"username": mgr_uname, "pin": "2222"})
    _post("/auth/change-pin", token=r2.json()["token"], json={"pin": "2323"})
    r3 = _post("/auth/login", json={"username": mgr_uname, "pin": "2323"})
    STATE["manager_token"] = r3.json()["token"]

    # Technician
    t_uname = f"ttech_{uuid.uuid4().hex[:6]}"
    r = _post("/users", token=admin_token,
              json={"username": t_uname, "name": "TEST_Tech", "role": "technician", "pin": "3333"})
    assert r.status_code == 200, r.text
    r2 = _post("/auth/login", json={"username": t_uname, "pin": "3333"})
    _post("/auth/change-pin", token=r2.json()["token"], json={"pin": "3434"})
    r3 = _post("/auth/login", json={"username": t_uname, "pin": "3434"})
    STATE["tech_token"] = r3.json()["token"]

    # Customer
    r = _post("/customers", token=admin_token,
              json={"name": "TEST_Cust_" + uuid.uuid4().hex[:5], "mobile": "9998887777",
                    "address": "Addr", "city": "Bangalore"})
    assert r.status_code == 200, r.text
    STATE["customer_id"] = r.json()["id"]
    yield


# =========================
# Feature 1: Reminder reschedule
# =========================
class TestReminderReschedule:
    def test_01_create_reminder(self):
        due = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        r = _post("/reminders", token=STATE["admin_token"],
                  json={"customer_id": STATE["customer_id"], "service_type": "Termite", "due_date": due})
        assert r.status_code == 200, r.text
        STATE["reminder_id"] = r.json()["id"]
        STATE["reminder_original_due"] = due

    def test_02_reschedule_endpoint_future(self):
        """POST /reminders/{id}/reschedule with future date => status='rescheduled', previous_due_date, rescheduled_at."""
        new_due = (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()
        r = _post(f"/reminders/{STATE['reminder_id']}/reschedule",
                  token=STATE["admin_token"], json={"due_date": new_due})
        assert r.status_code == 200, r.text
        # Verify via GET /reminders
        r2 = _get("/reminders", token=STATE["admin_token"])
        assert r2.status_code == 200
        by_id = {x["id"]: x for x in r2.json()}
        rem = by_id[STATE["reminder_id"]]
        assert rem["status"] == "rescheduled", f"Expected rescheduled, got {rem['status']}"
        assert rem.get("previous_due_date") == STATE["reminder_original_due"], \
            f"previous_due_date mismatch: {rem.get('previous_due_date')} vs {STATE['reminder_original_due']}"
        assert rem.get("rescheduled_at"), "rescheduled_at missing"
        assert rem["due_date"] == new_due
        # computed should be 'rescheduled' since due_date is future
        assert rem.get("computed") == "rescheduled", f"Expected computed=rescheduled, got {rem.get('computed')}"

    def test_03_reschedule_to_past_computed_overdue(self):
        """When rescheduled but new due_date is in the past, computed should be 'overdue'."""
        # Create a fresh reminder
        due = (datetime.now(timezone.utc) + timedelta(days=15)).isoformat()
        r = _post("/reminders", token=STATE["admin_token"],
                  json={"customer_id": STATE["customer_id"], "service_type": "Cockroach", "due_date": due})
        rid = r.json()["id"]
        # Reschedule to past
        past_due = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        r2 = _post(f"/reminders/{rid}/reschedule", token=STATE["admin_token"], json={"due_date": past_due})
        assert r2.status_code == 200
        # GET
        r3 = _get("/reminders", token=STATE["admin_token"])
        by_id = {x["id"]: x for x in r3.json()}
        rem = by_id[rid]
        assert rem["status"] == "rescheduled"
        # computed for past date + rescheduled: per code, computed only becomes 'rescheduled' when due >= now,
        # else it falls to overdue branch
        assert rem.get("computed") == "overdue", f"Expected overdue, got {rem.get('computed')}"

    def test_04_patch_changed_due_date_auto_reschedule(self):
        """PATCH /reminders/{id} with changed due_date => status auto-set to 'rescheduled' and previous_due_date recorded."""
        due_initial = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()
        r = _post("/reminders", token=STATE["admin_token"],
                  json={"customer_id": STATE["customer_id"], "service_type": "Rodent", "due_date": due_initial})
        rid = r.json()["id"]

        new_due = (datetime.now(timezone.utc) + timedelta(days=40)).isoformat()
        r2 = _patch(f"/reminders/{rid}", token=STATE["admin_token"],
                    json={"customer_id": STATE["customer_id"], "service_type": "Rodent", "due_date": new_due})
        assert r2.status_code == 200, r2.text

        r3 = _get("/reminders", token=STATE["admin_token"])
        by_id = {x["id"]: x for x in r3.json()}
        rem = by_id[rid]
        assert rem["status"] == "rescheduled", f"Expected rescheduled, got {rem['status']}"
        assert rem.get("previous_due_date") == due_initial
        assert rem.get("rescheduled_at")
        assert rem["due_date"] == new_due

    def test_05_patch_same_due_date_no_reschedule(self):
        """PATCH /reminders/{id} with unchanged due_date => status NOT flipped."""
        due = (datetime.now(timezone.utc) + timedelta(days=25)).isoformat()
        r = _post("/reminders", token=STATE["admin_token"],
                  json={"customer_id": STATE["customer_id"], "service_type": "Mosquito", "due_date": due})
        rid = r.json()["id"]

        # PATCH with same due_date
        r2 = _patch(f"/reminders/{rid}", token=STATE["admin_token"],
                    json={"customer_id": STATE["customer_id"], "service_type": "Mosquito", "due_date": due})
        assert r2.status_code == 200

        r3 = _get("/reminders", token=STATE["admin_token"])
        by_id = {x["id"]: x for x in r3.json()}
        rem = by_id[rid]
        assert rem["status"] != "rescheduled", f"Status should not flip; got {rem['status']}"
        assert "previous_due_date" not in rem or rem.get("previous_due_date") in (None, "")

    def test_06_reschedule_creates_audit_entry(self):
        """Verify reschedule action creates an audit entry with entity='reminder', action='reschedule'."""
        # Trigger a fresh reschedule so we know a log exists
        due = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        r = _post("/reminders", token=STATE["admin_token"],
                  json={"customer_id": STATE["customer_id"], "service_type": "Termite", "due_date": due})
        rid = r.json()["id"]
        new_due = (datetime.now(timezone.utc) + timedelta(days=50)).isoformat()
        r2 = _post(f"/reminders/{rid}/reschedule", token=STATE["admin_token"], json={"due_date": new_due})
        assert r2.status_code == 200

        # Fetch audit logs
        r3 = _get("/audit-logs", token=STATE["admin_token"], params={"limit": 200})
        assert r3.status_code == 200, r3.text
        logs = r3.json()
        matching = [l for l in logs if l.get("entity") == "reminder"
                    and l.get("action") == "reschedule"
                    and l.get("entity_id") == rid]
        assert len(matching) >= 1, f"No reschedule audit entry for rid={rid}. Logs sample: {logs[:3]}"


# =========================
# Feature 2: /reports/summary extra fields
# =========================
class TestReportsSummary:
    def test_01_admin_gets_all_new_keys(self):
        r = _get("/reports/summary", token=STATE["admin_token"])
        assert r.status_code == 200, r.text
        d = r.json()
        expected_keys = [
            "total_revenue", "month_revenue", "by_service_type", "technicians",
            "daily_services", "monthly_services",
            "pending_services_count", "amc_count", "amc_services_count", "customers_count",
            "top_customers",
        ]
        for k in expected_keys:
            assert k in d, f"Missing key: {k}"

        # Validate shapes
        assert isinstance(d["daily_services"], list) and len(d["daily_services"]) == 7, \
            f"daily_services should have 7 items, got {len(d['daily_services'])}"
        for item in d["daily_services"]:
            assert "date" in item and "count" in item

        assert isinstance(d["monthly_services"], list) and len(d["monthly_services"]) == 6, \
            f"monthly_services should have 6 items, got {len(d['monthly_services'])}"
        for item in d["monthly_services"]:
            assert "month" in item and "count" in item and "revenue" in item

        assert isinstance(d["pending_services_count"], int)
        assert isinstance(d["amc_count"], int)
        assert isinstance(d["amc_services_count"], int)
        assert isinstance(d["customers_count"], int)
        assert isinstance(d["top_customers"], list)
        for tc in d["top_customers"]:
            assert "id" in tc and "name" in tc and "services" in tc and "revenue" in tc

    def test_02_manager_forbidden(self):
        r = _get("/reports/summary", token=STATE["manager_token"])
        assert r.status_code == 403, r.text

    def test_03_technician_forbidden(self):
        r = _get("/reports/summary", token=STATE["tech_token"])
        assert r.status_code == 403, r.text


# =========================
# Feature 3: /audit-logs admin-only
# =========================
class TestAuditLogs:
    def test_01_admin_can_fetch(self):
        r = _get("/audit-logs", token=STATE["admin_token"])
        assert r.status_code == 200, r.text
        logs = r.json()
        assert isinstance(logs, list)
        assert len(logs) > 0, "Expected at least some audit logs after prior actions"
        # Validate first entry shape
        entry = logs[0]
        for k in ("entity", "action", "user_name", "at"):
            assert k in entry, f"Missing key {k} in audit log entry"
        # changes may be dict or None
        assert "changes" in entry

    def test_02_manager_forbidden(self):
        r = _get("/audit-logs", token=STATE["manager_token"])
        assert r.status_code == 403, r.text

    def test_03_technician_forbidden(self):
        r = _get("/audit-logs", token=STATE["tech_token"])
        assert r.status_code == 403, r.text
