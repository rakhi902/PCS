"""
Backend tests for the "complete service without photos" business rule.

Requirement (iteration-9):
- Photos are OPTIONAL for marking a service completed.
- POST /api/services/{id}/complete   -> 200 with 0/1/2 photos.
- PATCH /api/services/{id} {status:'completed'} by admin/manager -> 200 with 0 photos
  (previously 400).
- Regression: Termite auto-reminder is still created when a Termite service is completed,
  regardless of photo presence.
- Regression: technician cannot un-complete via PATCH {status:'pending'} -> 400.
- Regression: technician can still toggle payment_status on a completed service.
"""
import io
import os
import uuid
import pytest
import requests

BASE_URL = os.environ["EXPO_BACKEND_URL"].rstrip("/")
ADMIN_USER, ADMIN_PIN = "admin", "1234"
SUFFIX = uuid.uuid4().hex[:8]


# ---------- helpers ----------
def _auth(session, token):
    session.headers.update({"Authorization": f"Bearer {token}"})


def _login(username, pin):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"username": username, "pin": pin}, timeout=30)
    assert r.status_code == 200, f"login {username} failed: {r.status_code} {r.text}"
    return r.json()["token"]


def _reset_admin_pin_if_needed():
    """Ensure admin/1234 works and must_change_pin=false so the token has full rights."""
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"username": ADMIN_USER, "pin": ADMIN_PIN}, timeout=30)
    if r.status_code == 200:
        tok = r.json()["token"]
        # ensure must_change_pin is false so admin permissions are unaffected
        if r.json()["user"].get("must_change_pin"):
            requests.post(f"{BASE_URL}/api/auth/change-pin",
                          headers={"Authorization": f"Bearer {tok}"},
                          json={"pin": ADMIN_PIN}, timeout=30)
        return
    pytest.skip("Admin login failed; cannot proceed")


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin():
    _reset_admin_pin_if_needed()
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    _auth(s, _login(ADMIN_USER, ADMIN_PIN))
    return s


@pytest.fixture(scope="module")
def manager(admin):
    username = f"tmgr_{SUFFIX}"
    r = admin.post(f"{BASE_URL}/api/users",
                   json={"username": username, "name": "TEST Mgr",
                         "role": "manager", "pin": "1111"})
    assert r.status_code == 200, r.text
    # First login triggers must_change_pin flow; change PIN so subsequent calls carry a
    # normal manager token (change-pin is required only via UI, but token already works).
    token = _login(username, "1111")
    requests.post(f"{BASE_URL}/api/auth/change-pin",
                  headers={"Authorization": f"Bearer {token}"},
                  json={"pin": "2222"}, timeout=30)
    token = _login(username, "2222")
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    _auth(s, token)
    return s


@pytest.fixture(scope="module")
def technician(admin):
    username = f"ttech_{SUFFIX}"
    r = admin.post(f"{BASE_URL}/api/users",
                   json={"username": username, "name": "TEST Tech",
                         "role": "technician", "pin": "1111"})
    assert r.status_code == 200, r.text
    tok = _login(username, "1111")
    requests.post(f"{BASE_URL}/api/auth/change-pin",
                  headers={"Authorization": f"Bearer {tok}"},
                  json={"pin": "2222"}, timeout=30)
    tok = _login(username, "2222")
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    _auth(s, tok)
    # attach id (fetch /auth/me)
    me = s.get(f"{BASE_URL}/api/auth/me").json()
    s.user_id = me["id"]  # type: ignore[attr-defined]
    return s


@pytest.fixture(scope="module")
def customer(admin):
    r = admin.post(f"{BASE_URL}/api/customers",
                   json={"name": f"TEST_Cust_{SUFFIX}", "mobile": "9000000000",
                         "address": "1 Test Street"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ---------- factory ----------
def _make_service(admin, customer_id, technician_id, service_type="Cockroach"):
    r = admin.post(f"{BASE_URL}/api/services", json={
        "customer_id": customer_id,
        "service_type": service_type,
        "scheduled_date": "2026-01-15T10:00:00+00:00",
        "technician_id": technician_id,
        "charges": 500,
    })
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _upload_photo(sess, sid, phase):
    files = {"file": ("img.jpg", io.BytesIO(b"\xff\xd8\xffFAKEJPG"), "image/jpeg")}
    data = {"phase": phase}
    # strip Content-Type header so requests sets multipart boundary
    h = {k: v for k, v in sess.headers.items() if k.lower() != "content-type"}
    r = requests.post(f"{BASE_URL}/api/services/{sid}/photos",
                      headers=h, files=files, data=data, timeout=30)
    assert r.status_code == 200, f"photo upload failed: {r.status_code} {r.text}"


# =========================================================================
# 1) Technician POST /complete with NO photos -> 200 and status='completed'
# =========================================================================
class TestTechnicianCompleteNoPhotos:
    def test_complete_with_no_photos(self, admin, technician, customer):
        sid = _make_service(admin, customer, technician.user_id)  # type: ignore[attr-defined]
        r = technician.post(f"{BASE_URL}/api/services/{sid}/complete",
                            json={"medicine": "Fipronil", "quantity": "1L"})
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        # Verify persistence
        s = admin.get(f"{BASE_URL}/api/services/{sid}").json()
        assert s["status"] == "completed"
        assert s.get("completed_at")
        assert s.get("medicine") == "Fipronil"
        assert (s.get("photos") or {}).get("before", []) == []
        assert (s.get("photos") or {}).get("after", []) == []

    def test_complete_with_only_before_photo(self, admin, technician, customer):
        sid = _make_service(admin, customer, technician.user_id)  # type: ignore[attr-defined]
        _upload_photo(technician, sid, "before")
        r = technician.post(f"{BASE_URL}/api/services/{sid}/complete", json={})
        assert r.status_code == 200, r.text
        s = admin.get(f"{BASE_URL}/api/services/{sid}").json()
        assert s["status"] == "completed"
        assert len(s["photos"]["before"]) == 1
        assert s["photos"]["after"] == []

    def test_complete_with_only_after_photo(self, admin, technician, customer):
        sid = _make_service(admin, customer, technician.user_id)  # type: ignore[attr-defined]
        _upload_photo(technician, sid, "after")
        r = technician.post(f"{BASE_URL}/api/services/{sid}/complete", json={})
        assert r.status_code == 200, r.text
        s = admin.get(f"{BASE_URL}/api/services/{sid}").json()
        assert s["status"] == "completed"
        assert s["photos"]["before"] == []
        assert len(s["photos"]["after"]) == 1

    def test_complete_with_both_photos(self, admin, technician, customer):
        sid = _make_service(admin, customer, technician.user_id)  # type: ignore[attr-defined]
        _upload_photo(technician, sid, "before")
        _upload_photo(technician, sid, "after")
        r = technician.post(f"{BASE_URL}/api/services/{sid}/complete", json={})
        assert r.status_code == 200, r.text
        s = admin.get(f"{BASE_URL}/api/services/{sid}").json()
        assert s["status"] == "completed"
        assert len(s["photos"]["before"]) == 1
        assert len(s["photos"]["after"]) == 1


# =========================================================================
# 2) Manager/Admin PATCH status='completed' with NO photos -> 200 (was 400)
# =========================================================================
class TestManagerAdminPatchCompleteNoPhotos:
    def test_manager_patch_complete_no_photos(self, admin, manager, technician, customer):
        sid = _make_service(admin, customer, technician.user_id)  # type: ignore[attr-defined]
        r = manager.patch(f"{BASE_URL}/api/services/{sid}",
                          json={"status": "completed"})
        assert r.status_code == 200, r.text
        s = admin.get(f"{BASE_URL}/api/services/{sid}").json()
        assert s["status"] == "completed"
        assert s.get("completed_at")

    def test_admin_patch_complete_no_photos(self, admin, technician, customer):
        sid = _make_service(admin, customer, technician.user_id)  # type: ignore[attr-defined]
        r = admin.patch(f"{BASE_URL}/api/services/{sid}",
                        json={"status": "completed"})
        assert r.status_code == 200, r.text
        s = admin.get(f"{BASE_URL}/api/services/{sid}").json()
        assert s["status"] == "completed"
        assert s.get("completed_at")


# =========================================================================
# 3) Regression: Termite auto-reminder created regardless of photos
# =========================================================================
class TestTermiteAutoReminderRegardlessOfPhotos:
    def _find_termite_reminder_for_service(self, admin, sid):
        rs = admin.get(f"{BASE_URL}/api/reminders").json()
        return [
            r for r in rs
            if r.get("source_service_id") == sid
            and r.get("service_type") == "Termite"
            and r.get("auto_source") == "termite_annual"
        ]

    def test_complete_endpoint_termite_no_photos_creates_reminder(
            self, admin, technician, customer):
        sid = _make_service(admin, customer, technician.user_id,  # type: ignore[attr-defined]
                            service_type="Termite")
        r = technician.post(f"{BASE_URL}/api/services/{sid}/complete", json={})
        assert r.status_code == 200, r.text
        matches = self._find_termite_reminder_for_service(admin, sid)
        assert len(matches) == 1, f"Expected exactly 1 auto-reminder, found {len(matches)}"
        assert matches[0].get("reminder_period_months") == 12

    def test_patch_termite_no_photos_creates_reminder(self, admin, technician):
        # Use a fresh customer to avoid the ±2-day dedup window from the previous
        # Termite completion (same customer would legitimately be blocked as duplicate).
        cr = admin.post(f"{BASE_URL}/api/customers",
                        json={"name": f"TEST_Cust_Termite2_{SUFFIX}",
                              "mobile": "9000000002"})
        assert cr.status_code == 200, cr.text
        cid2 = cr.json()["id"]
        sid = _make_service(admin, cid2, technician.user_id,  # type: ignore[attr-defined]
                            service_type="Termite")
        r = admin.patch(f"{BASE_URL}/api/services/{sid}",
                        json={"status": "completed"})
        assert r.status_code == 200, r.text
        matches = self._find_termite_reminder_for_service(admin, sid)
        assert len(matches) == 1, f"Expected exactly 1 auto-reminder, found {len(matches)}"


# =========================================================================
# 4) Regression: technician cannot un-complete a completed service
# =========================================================================
class TestTechnicianCannotUncomplete:
    def test_uncomplete_via_patch_forbidden(self, admin, technician, customer):
        sid = _make_service(admin, customer, technician.user_id)  # type: ignore[attr-defined]
        r = technician.post(f"{BASE_URL}/api/services/{sid}/complete", json={})
        assert r.status_code == 200

        # Try to set back to pending
        r = technician.patch(f"{BASE_URL}/api/services/{sid}",
                             json={"status": "pending"})
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"

        # DB status unchanged
        s = admin.get(f"{BASE_URL}/api/services/{sid}").json()
        assert s["status"] == "completed"


# =========================================================================
# 5) Regression: technician can still toggle payment_status on completed service
# =========================================================================
class TestTechnicianPaymentStatusToggle:
    def test_toggle_payment_after_completion(self, admin, technician, customer):
        sid = _make_service(admin, customer, technician.user_id)  # type: ignore[attr-defined]
        r = technician.post(f"{BASE_URL}/api/services/{sid}/complete", json={})
        assert r.status_code == 200

        r = technician.patch(f"{BASE_URL}/api/services/{sid}",
                             json={"payment_status": "paid"})
        assert r.status_code == 200, r.text

        s = admin.get(f"{BASE_URL}/api/services/{sid}").json()
        assert s["status"] == "completed"
        assert s["payment_status"] == "paid"
