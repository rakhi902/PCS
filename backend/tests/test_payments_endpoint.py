"""Tests for GET /api/payments and payment marker attribution on PATCH /api/services/{id}.

Covers:
- Auth/role gating on /api/payments (admin 200, manager 200, technician 403, unauth 401)
- Shape: pending, paid, total_pending, total_paid, count_pending, count_paid
- AMC-generated services are excluded from /api/payments
- Non-AMC services with unpaid/pending appear in pending; totals sum correctly
- Non-AMC services with paid appear in paid
- payment_marked_by fields captured when technician / admin / manager change payment_status
- Regression: technician can mark payment on completed service; photo-optional /complete works;
  role authz on services list; Termite auto-reminder still created on completion.
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = (os.environ.get("EXPO_BACKEND_URL") or "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

SUFFIX = uuid.uuid4().hex[:8]


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"username": "admin", "pin": "1234"}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text}")
    return r.json()["token"]


@pytest.fixture(scope="module")
def manager_and_tech(admin_token):
    """Create a manager + technician; return their (id, username, name, token)."""
    mgr_u = f"TESTpaymgr_{SUFFIX}"
    tec_u = f"TESTpaytec_{SUFFIX}"
    # Manager
    rm = requests.post(f"{API}/users", headers=_h(admin_token),
                      json={"username": mgr_u, "name": "TEST Pay Mgr", "role": "manager", "pin": "1111"}, timeout=15)
    assert rm.status_code == 200, rm.text
    mgr_id = rm.json()["id"]
    # Technician
    rt = requests.post(f"{API}/users", headers=_h(admin_token),
                      json={"username": tec_u, "name": "TEST Pay Tech", "role": "technician", "pin": "1111"}, timeout=15)
    assert rt.status_code == 200, rt.text
    tec_id = rt.json()["id"]

    # Login with force must_change_pin
    def _login_and_change(u):
        lr = requests.post(f"{API}/auth/login", json={"username": u, "pin": "1111"}, timeout=15)
        assert lr.status_code == 200, lr.text
        tok = lr.json()["token"]
        cp = requests.post(f"{API}/auth/change-pin", headers=_h(tok), json={"pin": "2222"}, timeout=15)
        assert cp.status_code == 200, cp.text
        lr2 = requests.post(f"{API}/auth/login", json={"username": u, "pin": "2222"}, timeout=15)
        return lr2.json()["token"]

    mgr_token = _login_and_change(mgr_u)
    tec_token = _login_and_change(tec_u)
    return {
        "manager": {"id": mgr_id, "username": mgr_u, "name": "TEST Pay Mgr", "token": mgr_token},
        "technician": {"id": tec_id, "username": tec_u, "name": "TEST Pay Tech", "token": tec_token},
    }


@pytest.fixture(scope="module")
def customer_id(admin_token):
    r = requests.post(f"{API}/customers", headers=_h(admin_token),
                      json={"name": f"TEST_Pay_Cust_{SUFFIX}", "mobile": "9000000000",
                            "address": "Somewhere", "city": "City"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _create_service(admin_token, customer_id, tech_id=None, charges=500.0, payment_status="unpaid",
                    service_type="Cockroach"):
    body = {
        "customer_id": customer_id, "service_type": service_type,
        "scheduled_date": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "charges": charges, "payment_status": payment_status,
    }
    if tech_id:
        body["technician_id"] = tech_id
    r = requests.post(f"{API}/services", headers=_h(admin_token), json=body, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["id"]


# --- 1. Authz / role tests on /api/payments ---

class TestPaymentsAuthz:
    def test_unauth_returns_401(self):
        r = requests.get(f"{API}/payments", timeout=15)
        assert r.status_code == 401

    def test_admin_returns_200_and_shape(self, admin_token):
        r = requests.get(f"{API}/payments", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("pending", "paid", "total_pending", "total_paid", "count_pending", "count_paid"):
            assert k in data, f"missing key {k} in response: {list(data.keys())}"
        assert isinstance(data["pending"], list)
        assert isinstance(data["paid"], list)
        assert isinstance(data["count_pending"], int)
        assert isinstance(data["count_paid"], int)
        assert isinstance(data["total_pending"], (int, float))
        assert isinstance(data["total_paid"], (int, float))

    def test_manager_returns_200(self, manager_and_tech):
        tok = manager_and_tech["manager"]["token"]
        r = requests.get(f"{API}/payments", headers=_h(tok), timeout=20)
        assert r.status_code == 200, r.text
        assert "pending" in r.json() and "paid" in r.json()

    def test_technician_returns_403(self, manager_and_tech):
        tok = manager_and_tech["technician"]["token"]
        r = requests.get(f"{API}/payments", headers=_h(tok), timeout=15)
        assert r.status_code == 403, r.text


# --- 2. AMC exclusion ---

class TestAMCExclusion:
    def test_amc_services_never_in_payments(self, admin_token, customer_id):
        # Create AMC with monthly frequency -> generates several services
        start = datetime.now(timezone.utc) - timedelta(days=1)
        end = start + timedelta(days=95)  # ~3 months → ~4 monthly svcs
        r = requests.post(f"{API}/amc", headers=_h(admin_token),
                          json={"customer_id": customer_id, "service_type": "Cockroach",
                                "start_date": start.isoformat(), "end_date": end.isoformat(),
                                "frequency": "monthly", "contract_amount": 5000}, timeout=20)
        assert r.status_code == 200, r.text
        amc = r.json()
        assert amc.get("generated", 0) >= 2, f"expected >=2 generated svcs, got {amc.get('generated')}"
        amc_id = amc["id"]

        # Collect all amc-generated service ids
        det = requests.get(f"{API}/amc/{amc_id}", headers=_h(admin_token), timeout=15)
        assert det.status_code == 200
        amc_svc_ids = {s["id"] for s in det.json()["services"]}
        assert amc_svc_ids, "AMC produced no services"

        # /payments must NOT contain any of them
        pay = requests.get(f"{API}/payments", headers=_h(admin_token), timeout=20).json()
        all_returned = {s["id"] for s in pay["pending"]} | {s["id"] for s in pay["paid"]}
        overlap = amc_svc_ids & all_returned
        assert not overlap, f"AMC-generated services leaked into /payments: {overlap}"


# --- 3. Pending/Paid grouping + totals ---

class TestGroupingAndTotals:
    def test_unpaid_and_pending_appear_in_pending_with_correct_totals(self, admin_token, customer_id):
        pay0 = requests.get(f"{API}/payments", headers=_h(admin_token), timeout=20).json()
        base_pending_sum = pay0["total_pending"]
        base_pending_cnt = pay0["count_pending"]

        s1 = _create_service(admin_token, customer_id, charges=111.0, payment_status="unpaid")
        s2 = _create_service(admin_token, customer_id, charges=222.5, payment_status="pending")

        pay = requests.get(f"{API}/payments", headers=_h(admin_token), timeout=20).json()
        ids_pending = {s["id"] for s in pay["pending"]}
        assert s1 in ids_pending
        assert s2 in ids_pending
        assert pay["count_pending"] == base_pending_cnt + 2
        assert abs(pay["total_pending"] - (base_pending_sum + 111.0 + 222.5)) < 0.01

    def test_paid_service_appears_in_paid_with_correct_totals(self, admin_token, customer_id):
        pay0 = requests.get(f"{API}/payments", headers=_h(admin_token), timeout=20).json()
        base_paid_sum = pay0["total_paid"]
        base_paid_cnt = pay0["count_paid"]

        s = _create_service(admin_token, customer_id, charges=750.0, payment_status="paid")

        pay = requests.get(f"{API}/payments", headers=_h(admin_token), timeout=20).json()
        ids_paid = {s2["id"] for s2 in pay["paid"]}
        assert s in ids_paid
        assert pay["count_paid"] == base_paid_cnt + 1
        assert abs(pay["total_paid"] - (base_paid_sum + 750.0)) < 0.01


# --- 4. Attribution on PATCH payment_status ---

class TestAttribution:
    def _find_in_paid(self, admin_token, sid):
        pay = requests.get(f"{API}/payments", headers=_h(admin_token), timeout=20).json()
        for row in pay["paid"]:
            if row["id"] == sid:
                return row
        return None

    def test_technician_marks_paid_on_own_completed_service(self, admin_token, customer_id, manager_and_tech):
        tec = manager_and_tech["technician"]
        # Assign service to technician
        sid = _create_service(admin_token, customer_id, tech_id=tec["id"], charges=300.0,
                              payment_status="unpaid")
        # technician completes it (photos optional)
        c = requests.post(f"{API}/services/{sid}/complete", headers=_h(tec["token"]),
                          json={"medicine": "X", "quantity": "1L"}, timeout=15)
        assert c.status_code == 200, c.text
        # technician marks paid
        p = requests.patch(f"{API}/services/{sid}", headers=_h(tec["token"]),
                           json={"payment_status": "paid"}, timeout=15)
        assert p.status_code == 200, p.text

        row = self._find_in_paid(admin_token, sid)
        assert row is not None, "service not found in /payments paid list"
        assert row.get("payment_marked_by") == tec["id"]
        assert row.get("payment_marked_by_name") == tec["name"]
        assert row.get("payment_marked_by_role") == "technician"
        assert row.get("payment_marked_at"), "payment_marked_at not set"
        # Verify GET single service also carries attribution
        gs = requests.get(f"{API}/services/{sid}", headers=_h(admin_token), timeout=15).json()
        assert gs.get("payment_marked_by_role") == "technician"

    def test_admin_marks_paid_attribution(self, admin_token, customer_id):
        sid = _create_service(admin_token, customer_id, charges=400.0, payment_status="unpaid")
        p = requests.patch(f"{API}/services/{sid}", headers=_h(admin_token),
                           json={"payment_status": "paid"}, timeout=15)
        assert p.status_code == 200, p.text
        row = self._find_in_paid(admin_token, sid)
        assert row is not None
        assert row.get("payment_marked_by_role") == "admin"
        assert row.get("payment_marked_by_name") == "Owner"
        assert row.get("payment_marked_at")

    def test_manager_marks_paid_attribution(self, admin_token, customer_id, manager_and_tech):
        mgr = manager_and_tech["manager"]
        sid = _create_service(admin_token, customer_id, charges=550.0, payment_status="unpaid")
        p = requests.patch(f"{API}/services/{sid}", headers=_h(mgr["token"]),
                           json={"payment_status": "paid"}, timeout=15)
        assert p.status_code == 200, p.text
        row = TestAttribution()._find_in_paid(admin_token, sid)
        assert row is not None
        assert row.get("payment_marked_by") == mgr["id"]
        assert row.get("payment_marked_by_name") == mgr["name"]
        assert row.get("payment_marked_by_role") == "manager"
        assert row.get("payment_marked_at")


# --- 5. Regressions ---

class TestRegressions:
    def test_complete_without_photos_still_works(self, admin_token, customer_id, manager_and_tech):
        tec = manager_and_tech["technician"]
        sid = _create_service(admin_token, customer_id, tech_id=tec["id"], charges=100.0)
        r = requests.post(f"{API}/services/{sid}/complete", headers=_h(tec["token"]), json={}, timeout=15)
        assert r.status_code == 200, r.text
        gs = requests.get(f"{API}/services/{sid}", headers=_h(admin_token), timeout=15).json()
        assert gs["status"] == "completed"

    def test_technician_cannot_list_payments(self, manager_and_tech):
        tok = manager_and_tech["technician"]["token"]
        r = requests.get(f"{API}/payments", headers=_h(tok), timeout=15)
        assert r.status_code == 403

    def test_technician_cannot_list_customers(self, manager_and_tech):
        tok = manager_and_tech["technician"]["token"]
        r = requests.get(f"{API}/customers", headers=_h(tok), timeout=15)
        assert r.status_code == 403

    def test_termite_reminder_created_on_completion(self, admin_token, manager_and_tech):
        # Fresh customer to avoid dedup window collisions with other termite tests
        cr = requests.post(f"{API}/customers", headers=_h(admin_token),
                           json={"name": f"TEST_TermitePay_{SUFFIX}", "mobile": "9111000222"}, timeout=15).json()
        cid = cr["id"]
        tec = manager_and_tech["technician"]
        sid = _create_service(admin_token, cid, tech_id=tec["id"], charges=250.0, service_type="Termite")
        c = requests.post(f"{API}/services/{sid}/complete", headers=_h(tec["token"]), json={}, timeout=15)
        assert c.status_code == 200
        rems = requests.get(f"{API}/reminders", headers=_h(admin_token), timeout=15).json()
        auto = [r for r in rems if r.get("source_service_id") == sid]
        assert len(auto) == 1, f"expected 1 termite reminder, got {len(auto)}"
        assert auto[0].get("auto_source") == "termite_annual"
        assert auto[0].get("reminder_period_months") == 12
