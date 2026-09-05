"""Focused backend tests for:
  - Termite auto-reminder on service completion (via /complete and via PATCH status=completed)
  - Duplicate prevention window
  - Non-Termite service completion does NOT create termite reminder
  - AMC-generated pending services + technician assignment via PATCH
  - Admin editing pending service (customer, service_type, dates, charges)
"""
import os
import io
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = (
    os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or os.environ.get("EXPO_BACKEND_URL")
    or "https://pest-control-mgmt.preview.emergentagent.com"
).rstrip("/")
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


def _login_admin():
    for pin in ("1234", "9999"):
        r = _post("/auth/login", json={"username": "admin", "pin": pin})
        if r.status_code == 200:
            data = r.json()
            token = data["token"]
            if data["user"].get("must_change_pin"):
                _post("/auth/change-pin", token=token, json={"pin": "9999"})
                r2 = _post("/auth/login", json={"username": "admin", "pin": "9999"})
                token = r2.json()["token"]
            return token
    raise RuntimeError("Admin login failed with both known PINs")


def _upload_photo(sid, token, phase):
    img = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    files = {"file": (f"{phase}.jpg", io.BytesIO(img), "image/jpeg")}
    return requests.post(
        f"{API}/services/{sid}/photos",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
        data={"phase": phase},
        timeout=60,
    )


# =========================
# Setup fixture-like class
# =========================
class Test00Setup:
    def test_00_admin_login(self):
        STATE["admin_token"] = _login_admin()
        assert STATE["admin_token"]

    def test_01_create_technician(self):
        uname = f"tech_{uuid.uuid4().hex[:6]}"
        r = _post("/users", token=STATE["admin_token"],
                  json={"username": uname, "name": "TEST_Tech", "role": "technician", "pin": "3333"})
        assert r.status_code == 200, r.text
        STATE["tech_id"] = r.json()["id"]
        # login + change pin
        rl = _post("/auth/login", json={"username": uname, "pin": "3333"})
        tok = rl.json()["token"]
        _post("/auth/change-pin", token=tok, json={"pin": "3434"})
        r2 = _post("/auth/login", json={"username": uname, "pin": "3434"})
        STATE["tech_token"] = r2.json()["token"]

    def test_02_create_second_technician(self):
        uname = f"tech_{uuid.uuid4().hex[:6]}"
        r = _post("/users", token=STATE["admin_token"],
                  json={"username": uname, "name": "TEST_Tech2", "role": "technician", "pin": "3333"})
        assert r.status_code == 200, r.text
        STATE["tech2_id"] = r.json()["id"]

    def test_03_create_customer(self):
        r = _post("/customers", token=STATE["admin_token"],
                  json={"name": f"TEST_Cust_{uuid.uuid4().hex[:5]}", "mobile": "9998887777", "address": "A", "city": "Blr"})
        assert r.status_code == 200
        STATE["customer_id"] = r.json()["id"]

    def test_04_create_second_customer(self):
        r = _post("/customers", token=STATE["admin_token"],
                  json={"name": f"TEST_Cust2_{uuid.uuid4().hex[:5]}", "mobile": "8887776666", "address": "B", "city": "Blr"})
        assert r.status_code == 200
        STATE["customer2_id"] = r.json()["id"]


# =========================
# Termite auto-reminder on /complete
# =========================
class Test10TermiteCompleteReminder:
    def _create_service(self, service_type, tech_id, customer_id=None):
        sched = datetime.now(timezone.utc).isoformat()
        r = _post("/services", token=STATE["admin_token"], json={
            "customer_id": customer_id or STATE["customer_id"],
            "service_type": service_type,
            "scheduled_date": sched, "technician_id": tech_id, "charges": 1500,
        })
        assert r.status_code == 200, r.text
        return r.json()["id"]

    def test_01_complete_termite_via_complete_endpoint_creates_reminder(self):
        sid = self._create_service("Termite", STATE["tech_id"])
        STATE["termite_svc_1"] = sid
        # Upload before/after
        r1 = _upload_photo(sid, STATE["tech_token"], "before")
        r2 = _upload_photo(sid, STATE["tech_token"], "after")
        if r1.status_code == 500 or r2.status_code == 500:
            pytest.skip("Storage not configured")
        assert r1.status_code == 200 and r2.status_code == 200

        # Complete
        rc = _post(f"/services/{sid}/complete", token=STATE["tech_token"],
                   json={"medicine": "M", "quantity": "10"})
        assert rc.status_code == 200, rc.text

        # Get completed_at
        rg = _get(f"/services/{sid}", token=STATE["admin_token"])
        completed_at = rg.json()["completed_at"]
        cd = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        from dateutil.relativedelta import relativedelta
        expected_due = cd + relativedelta(years=1) - timedelta(days=7)

        # Fetch reminders and check one exists for this customer + Termite + auto_source
        rr = _get("/reminders", token=STATE["admin_token"])
        assert rr.status_code == 200
        matches = [
            r for r in rr.json()
            if r["customer_id"] == STATE["customer_id"]
            and r.get("service_type") == "Termite"
            and r.get("auto_source") == "termite_annual"
        ]
        assert len(matches) >= 1, f"No auto-created termite reminder found: {rr.json()}"
        rem = matches[0]
        assert rem["status"] == "upcoming"
        assert rem.get("source_service_id") == sid
        # due_date approximately expected_due (allow +/- 60s wall clock drift)
        rd = datetime.fromisoformat(rem["due_date"].replace("Z", "+00:00"))
        diff = abs((rd - expected_due).total_seconds())
        assert diff < 120, f"due_date drift {diff}s (rd={rd}, exp={expected_due})"
        STATE["termite_reminder_1_id"] = rem["id"]

    def test_02_second_termite_complete_same_customer_no_duplicate(self):
        # Create + complete another Termite for the same customer immediately
        sid = self._create_service("Termite", STATE["tech_id"])
        STATE["termite_svc_2"] = sid
        r1 = _upload_photo(sid, STATE["tech_token"], "before")
        r2 = _upload_photo(sid, STATE["tech_token"], "after")
        if r1.status_code == 500 or r2.status_code == 500:
            pytest.skip("Storage not configured")

        rc = _post(f"/services/{sid}/complete", token=STATE["tech_token"], json={})
        assert rc.status_code == 200

        rr = _get("/reminders", token=STATE["admin_token"])
        termite_for_customer = [
            r for r in rr.json()
            if r["customer_id"] == STATE["customer_id"]
            and r.get("service_type") == "Termite"
            and r.get("auto_source") == "termite_annual"
        ]
        assert len(termite_for_customer) == 1, (
            f"Expected exactly 1 termite reminder (dedup), got {len(termite_for_customer)}: "
            f"{[r['id'] for r in termite_for_customer]}"
        )

    def test_03_non_termite_complete_no_reminder(self):
        # Fresh customer to isolate
        sid = self._create_service("Cockroach", STATE["tech_id"], customer_id=STATE["customer2_id"])
        r1 = _upload_photo(sid, STATE["tech_token"], "before")
        r2 = _upload_photo(sid, STATE["tech_token"], "after")
        if r1.status_code == 500 or r2.status_code == 500:
            pytest.skip("Storage not configured")

        rc = _post(f"/services/{sid}/complete", token=STATE["tech_token"], json={})
        assert rc.status_code == 200

        rr = _get("/reminders", token=STATE["admin_token"])
        auto_for_c2 = [
            r for r in rr.json()
            if r["customer_id"] == STATE["customer2_id"]
            and r.get("auto_source") == "termite_annual"
        ]
        assert len(auto_for_c2) == 0, f"Non-termite completion should not create termite reminder: {auto_for_c2}"

    def test_04_admin_patch_status_completed_termite_creates_reminder(self):
        # Use a NEW customer to bypass dedup window
        r = _post("/customers", token=STATE["admin_token"],
                  json={"name": f"TEST_Cust3_{uuid.uuid4().hex[:5]}", "mobile": "7776665555",
                        "address": "C", "city": "Blr"})
        c3 = r.json()["id"]
        STATE["customer3_id"] = c3

        # Create Termite service assigned; upload photos as tech
        sched = datetime.now(timezone.utc).isoformat()
        rs = _post("/services", token=STATE["admin_token"], json={
            "customer_id": c3, "service_type": "Termite",
            "scheduled_date": sched, "technician_id": STATE["tech_id"], "charges": 2000,
        })
        assert rs.status_code == 200
        sid = rs.json()["id"]

        # Admin PATCH status -> completed (bypasses photo requirement)
        rp = _patch(f"/services/{sid}", token=STATE["admin_token"], json={"status": "completed"})
        assert rp.status_code == 200, rp.text

        rr = _get("/reminders", token=STATE["admin_token"])
        matches = [
            r for r in rr.json()
            if r["customer_id"] == c3
            and r.get("service_type") == "Termite"
            and r.get("auto_source") == "termite_annual"
        ]
        assert len(matches) == 1, f"Admin PATCH complete should create termite reminder, got {len(matches)}"
        assert matches[0]["status"] == "upcoming"


# =========================
# AMC generation + assignment
# =========================
class Test20AMCPendingAndAssign:
    def test_01_create_monthly_amc(self):
        # Fresh customer to avoid mixing with earlier services
        rc = _post("/customers", token=STATE["admin_token"],
                   json={"name": f"TEST_AMC_{uuid.uuid4().hex[:5]}", "mobile": "5554443333",
                         "address": "D", "city": "Blr"})
        assert rc.status_code == 200
        cid = rc.json()["id"]
        STATE["amc_customer_id"] = cid

        start = datetime.now(timezone.utc)
        end = start + timedelta(days=365)
        r = _post("/amc", token=STATE["admin_token"], json={
            "customer_id": cid, "service_type": "Cockroach",
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "frequency": "monthly", "contract_amount": 12000,
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["generated"] >= 12
        STATE["amc_id"] = d["id"]

    def test_02_amc_generated_pending_no_tech(self):
        r = _get("/services", token=STATE["admin_token"],
                 params={"status": "pending", "customer_id": STATE["amc_customer_id"]})
        assert r.status_code == 200
        amc_services = [s for s in r.json() if s.get("amc_id") == STATE["amc_id"]]
        assert len(amc_services) >= 12
        for s in amc_services:
            assert s["status"] == "pending", s
            assert s.get("technician_id") in (None, ""), s
        STATE["amc_pending_service_id"] = amc_services[0]["id"]

    def test_03_assign_technician_status_becomes_assigned(self):
        sid = STATE["amc_pending_service_id"]
        r = _patch(f"/services/{sid}", token=STATE["admin_token"],
                   json={"technician_id": STATE["tech_id"]})
        assert r.status_code == 200, r.text
        rg = _get(f"/services/{sid}", token=STATE["admin_token"])
        d = rg.json()
        assert d["technician_id"] == STATE["tech_id"]
        assert d["status"] == "assigned", f"Expected assigned, got {d['status']}"

    def test_04_reassign_technician_same_service(self):
        sid = STATE["amc_pending_service_id"]
        r = _patch(f"/services/{sid}", token=STATE["admin_token"],
                   json={"technician_id": STATE["tech2_id"]})
        assert r.status_code == 200, r.text
        rg = _get(f"/services/{sid}", token=STATE["admin_token"])
        d = rg.json()
        assert d["technician_id"] == STATE["tech2_id"]
        # still same id
        assert d["id"] == sid
        # status stays assigned (should not revert)
        assert d["status"] in ("assigned", "in_progress")

        # And there should be no duplicated services in the list for that scheduled slot
        r2 = _get("/services", token=STATE["admin_token"],
                  params={"customer_id": STATE["amc_customer_id"]})
        ids = [s["id"] for s in r2.json()]
        assert ids.count(sid) == 1


# =========================
# Admin edit pending service fields
# =========================
class Test30AdminEditPendingService:
    def test_01_admin_edit_all_fields(self):
        # Create pending service
        sched = datetime.now(timezone.utc).isoformat()
        r = _post("/services", token=STATE["admin_token"], json={
            "customer_id": STATE["customer_id"], "service_type": "Cockroach",
            "scheduled_date": sched, "charges": 500,
        })
        assert r.status_code == 200
        sid = r.json()["id"]
        assert r.json()["status"] == "pending"

        # Edit customer, service_type, scheduled_date, charges
        new_sched = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        rp = _patch(f"/services/{sid}", token=STATE["admin_token"], json={
            "customer_id": STATE["customer2_id"],
            "service_type": "Rodent",
            "scheduled_date": new_sched,
            "charges": 1234,
        })
        assert rp.status_code == 200, rp.text

        rg = _get(f"/services/{sid}", token=STATE["admin_token"])
        d = rg.json()
        assert d["customer_id"] == STATE["customer2_id"]
        assert d["service_type"] == "Rodent"
        assert d["scheduled_date"] == new_sched
        assert d.get("charges") == 1234

    def test_02_admin_edit_assigned_service_reassign_and_dates(self):
        sched = datetime.now(timezone.utc).isoformat()
        r = _post("/services", token=STATE["admin_token"], json={
            "customer_id": STATE["customer_id"], "service_type": "Mosquito",
            "scheduled_date": sched, "technician_id": STATE["tech_id"], "charges": 700,
        })
        assert r.status_code == 200
        sid = r.json()["id"]
        assert r.json()["status"] == "assigned"

        new_sched = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        rp = _patch(f"/services/{sid}", token=STATE["admin_token"], json={
            "technician_id": STATE["tech2_id"],
            "scheduled_date": new_sched,
            "charges": 900,
        })
        assert rp.status_code == 200, rp.text
        rg = _get(f"/services/{sid}", token=STATE["admin_token"])
        d = rg.json()
        assert d["technician_id"] == STATE["tech2_id"]
        assert d["scheduled_date"] == new_sched
        assert d.get("charges") == 900

    def test_03_admin_edit_in_progress_service(self):
        # Create + assign + tech marks in_progress
        sched = datetime.now(timezone.utc).isoformat()
        r = _post("/services", token=STATE["admin_token"], json={
            "customer_id": STATE["customer_id"], "service_type": "Cockroach",
            "scheduled_date": sched, "technician_id": STATE["tech_id"], "charges": 300,
        })
        sid = r.json()["id"]
        rt = _patch(f"/services/{sid}", token=STATE["tech_token"], json={"status": "in_progress"})
        assert rt.status_code == 200

        # Admin edits charges + service_type on in_progress
        rp = _patch(f"/services/{sid}", token=STATE["admin_token"], json={
            "service_type": "Termite",
            "charges": 4000,
        })
        assert rp.status_code == 200, rp.text
        rg = _get(f"/services/{sid}", token=STATE["admin_token"])
        d = rg.json()
        assert d["service_type"] == "Termite"
        assert d.get("charges") == 4000
        assert d["status"] == "in_progress"
