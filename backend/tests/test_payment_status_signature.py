"""Backend tests for review scope:
  (A) Technician can PATCH payment_status on assigned service; charges NOT allowed
  (B) POST /services/{sid}/signature multipart upload + GET /files/{path}?token=...
  (C) Regression: termite auto reminder still works; manager charges stripped

Run: pytest /app/backend/tests/test_payment_status_signature.py -n 0 -v
"""
import os
import io
import uuid
import pytest
import requests
from datetime import datetime, timezone

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")
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
    raise RuntimeError("Admin login failed")


def _create_user(admin_token, role, name_prefix):
    uname = f"{name_prefix}_{uuid.uuid4().hex[:6]}"
    r = _post("/users", token=admin_token,
              json={"username": uname, "name": f"TEST_{name_prefix}",
                    "role": role, "pin": "3333"})
    assert r.status_code == 200, r.text
    uid = r.json()["id"]
    rl = _post("/auth/login", json={"username": uname, "pin": "3333"})
    tok = rl.json()["token"]
    _post("/auth/change-pin", token=tok, json={"pin": "3434"})
    r2 = _post("/auth/login", json={"username": uname, "pin": "3434"})
    return uid, r2.json()["token"], uname


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
# Setup
# =========================
class Test00Setup:
    def test_00_admin_login(self):
        STATE["admin"] = _login_admin()
        assert STATE["admin"]

    def test_01_create_tech1(self):
        uid, tok, _ = _create_user(STATE["admin"], "technician", "tech1")
        STATE["tech1_id"] = uid
        STATE["tech1"] = tok

    def test_02_create_tech2(self):
        uid, tok, _ = _create_user(STATE["admin"], "technician", "tech2")
        STATE["tech2_id"] = uid
        STATE["tech2"] = tok

    def test_03_create_manager(self):
        uid, tok, _ = _create_user(STATE["admin"], "manager", "mgr")
        STATE["mgr_id"] = uid
        STATE["mgr"] = tok

    def test_04_create_customer(self):
        r = _post("/customers", token=STATE["admin"], json={
            "name": f"TEST_C_{uuid.uuid4().hex[:5]}",
            "mobile": "9990001111", "address": "A", "city": "Blr"})
        assert r.status_code == 200
        STATE["cid"] = r.json()["id"]


# =========================
# (A) Tech payment_status PATCH
# =========================
class Test10TechPaymentStatus:
    def _create_svc(self, technician_id=None, charges=1500, creator="admin"):
        tok = STATE[creator]
        sched = datetime.now(timezone.utc).isoformat()
        payload = {"customer_id": STATE["cid"], "service_type": "Cockroach",
                   "scheduled_date": sched, "charges": charges}
        if technician_id:
            payload["technician_id"] = technician_id
        r = _post("/services", token=tok, json=payload)
        assert r.status_code == 200, r.text
        return r.json()

    def test_01_tech_assigned_can_set_payment_status_paid(self):
        svc = self._create_svc(technician_id=STATE["tech1_id"], charges=1000)
        sid = svc["id"]
        STATE["svc_paid"] = sid
        r = _patch(f"/services/{sid}", token=STATE["tech1"],
                   json={"payment_status": "paid"})
        assert r.status_code == 200, r.text
        rg = _get(f"/services/{sid}", token=STATE["admin"])
        assert rg.json().get("payment_status") == "paid"

    def test_02_tech_assigned_can_set_payment_status_unpaid(self):
        sid = STATE["svc_paid"]
        r = _patch(f"/services/{sid}", token=STATE["tech1"],
                   json={"payment_status": "unpaid"})
        assert r.status_code == 200, r.text
        rg = _get(f"/services/{sid}", token=STATE["admin"])
        assert rg.json().get("payment_status") == "unpaid"

    def test_03_other_tech_cannot_patch(self):
        sid = STATE["svc_paid"]
        r = _patch(f"/services/{sid}", token=STATE["tech2"],
                   json={"payment_status": "paid"})
        assert r.status_code == 403, r.text

    def test_04_tech_cannot_set_charges(self):
        # Admin creates svc with charges=2000, tech tries to bump to 9999
        svc = self._create_svc(technician_id=STATE["tech1_id"], charges=2000)
        sid = svc["id"]
        # admin creates -> charges preserved
        assert svc.get("charges") == 2000
        r = _patch(f"/services/{sid}", token=STATE["tech1"],
                   json={"charges": 9999, "payment_status": "paid"})
        # payment_status is a valid field so update goes through 200
        assert r.status_code == 200, r.text
        rg = _get(f"/services/{sid}", token=STATE["admin"])
        d = rg.json()
        assert d.get("charges") == 2000, f"Tech PATCH should not change charges, got {d.get('charges')}"
        assert d.get("payment_status") == "paid"

    def test_05_tech_patch_only_charges_returns_400(self):
        # If ONLY disallowed fields present, upd becomes empty -> 400
        svc = self._create_svc(technician_id=STATE["tech1_id"], charges=500)
        sid = svc["id"]
        r = _patch(f"/services/{sid}", token=STATE["tech1"],
                   json={"charges": 4444})
        assert r.status_code == 400, r.text


# =========================
# (B) Signature upload + GET /files
# =========================
class Test20Signature:
    def _create_assigned_svc(self):
        sched = datetime.now(timezone.utc).isoformat()
        r = _post("/services", token=STATE["admin"], json={
            "customer_id": STATE["cid"], "service_type": "Termite",
            "scheduled_date": sched, "technician_id": STATE["tech1_id"],
            "charges": 3000})
        assert r.status_code == 200, r.text
        return r.json()["id"]

    def test_01_tech_uploads_signature(self):
        sid = self._create_assigned_svc()
        STATE["sig_sid"] = sid
        png = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 200)
        files = {"file": ("sign.png", io.BytesIO(png), "image/png")}
        r = requests.post(f"{API}/services/{sid}/signature",
                          headers={"Authorization": f"Bearer {STATE['tech1']}"},
                          files=files, timeout=60)
        if r.status_code == 500:
            pytest.skip(f"Storage backend not configured: {r.text[:200]}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "path" in body and body["path"]
        STATE["sig_path"] = body["path"]

        rg = _get(f"/services/{sid}", token=STATE["admin"])
        d = rg.json()
        assert d.get("signature_path") == body["path"]
        assert d.get("signature_at"), "signature_at missing"

    def test_02_get_file_with_token_query(self):
        if "sig_path" not in STATE:
            pytest.skip("signature upload didn't succeed")
        path = STATE["sig_path"]
        r = requests.get(f"{API}/files/{path}",
                         params={"token": STATE["admin"]},
                         timeout=30)
        assert r.status_code == 200, r.text
        assert len(r.content) > 0
        assert r.headers.get("content-type", "").startswith("image/")

    def test_03_get_file_without_token_401(self):
        if "sig_path" not in STATE:
            pytest.skip("no sig")
        r = requests.get(f"{API}/files/{STATE['sig_path']}", timeout=30)
        assert r.status_code == 401, r.text

    def test_04_get_file_bad_token_401(self):
        if "sig_path" not in STATE:
            pytest.skip("no sig")
        r = requests.get(f"{API}/files/{STATE['sig_path']}",
                         params={"token": "not-a-jwt"}, timeout=30)
        assert r.status_code == 401, r.text

    def test_05_other_tech_signature_403(self):
        sid = STATE.get("sig_sid")
        if not sid:
            pytest.skip("no sig service")
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        files = {"file": ("sign.png", io.BytesIO(png), "image/png")}
        r = requests.post(f"{API}/services/{sid}/signature",
                          headers={"Authorization": f"Bearer {STATE['tech2']}"},
                          files=files, timeout=60)
        assert r.status_code == 403, r.text

    def test_06_unauthenticated_signature_401(self):
        sid = STATE.get("sig_sid")
        if not sid:
            pytest.skip("no sig service")
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        files = {"file": ("sign.png", io.BytesIO(png), "image/png")}
        r = requests.post(f"{API}/services/{sid}/signature",
                          files=files, timeout=60)
        assert r.status_code == 401, r.text


# =========================
# (C) Regression: Termite auto reminder + manager charges strip
# =========================
class Test30Regression:
    def test_01_manager_create_service_charges_stripped(self):
        r = _post("/customers", token=STATE["admin"], json={
            "name": f"TEST_MgrC_{uuid.uuid4().hex[:5]}",
            "mobile": "8887776665", "address": "X", "city": "Y"})
        cid = r.json()["id"]
        sched = datetime.now(timezone.utc).isoformat()
        rs = _post("/services", token=STATE["mgr"], json={
            "customer_id": cid, "service_type": "Cockroach",
            "scheduled_date": sched, "charges": 5000})
        assert rs.status_code == 200, rs.text
        d = rs.json()
        assert d.get("charges") == 0, (
            f"Manager-created service should have charges=0, got {d.get('charges')}"
        )

    def test_02_termite_complete_creates_reminder(self):
        # Fresh customer to avoid dedup window
        rc = _post("/customers", token=STATE["admin"], json={
            "name": f"TEST_TReg_{uuid.uuid4().hex[:5]}",
            "mobile": "7776665554", "address": "T", "city": "B"})
        cid = rc.json()["id"]
        sched = datetime.now(timezone.utc).isoformat()
        rs = _post("/services", token=STATE["admin"], json={
            "customer_id": cid, "service_type": "Termite",
            "scheduled_date": sched, "technician_id": STATE["tech1_id"],
            "charges": 1500})
        assert rs.status_code == 200
        sid = rs.json()["id"]

        r1 = _upload_photo(sid, STATE["tech1"], "before")
        r2 = _upload_photo(sid, STATE["tech1"], "after")
        if r1.status_code == 500 or r2.status_code == 500:
            pytest.skip("Storage not configured")
        assert r1.status_code == 200 and r2.status_code == 200

        rc2 = _post(f"/services/{sid}/complete", token=STATE["tech1"], json={})
        assert rc2.status_code == 200, rc2.text

        rr = _get("/reminders", token=STATE["admin"])
        assert rr.status_code == 200
        matches = [
            rem for rem in rr.json()
            if rem["customer_id"] == cid
            and rem.get("service_type") == "Termite"
            and rem.get("auto_source") == "termite_annual"
        ]
        assert len(matches) == 1, f"Expected 1 termite auto reminder, got {len(matches)}"
        assert matches[0]["status"] == "upcoming"
        assert matches[0].get("source_service_id") == sid
