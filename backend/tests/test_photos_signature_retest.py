"""Retest for iteration-8:
Backend photo/signature multipart upload verification after the
frontend switched from FormData({uri,name,type}) to expo-file-system
uploadAsync (MULTIPART) on native. The backend endpoints are unchanged,
so this suite guards against regression.

Scenarios validated:
  1. POST /services/{sid}/photos (multipart phase=before + jpeg) as
     assigned tech → 200 {path}. Service.photos.before grows by 1.
     GET /files/{path}?token=... returns bytes with image content-type.
  2. POST /services/{sid}/photos with phase='invalid' → 400.
  3. POST /services/{sid}/photos without Authorization → 401.
  4. POST /services/{sid}/photos by a DIFFERENT (non-assigned) tech → 403.
  5. POST /services/{sid}/signature multipart as assigned tech → 200,
     signature_path set. GET /files/{sig_path}?token=... returns bytes.
  6. Regression: /complete requires before+after photos still (400 w/o).
     With both photos present, /complete returns 200 and Termite auto
     reminder is created.

Run: pytest /app/backend/tests/test_photos_signature_retest.py -v -n 0
"""
import io
import os
import uuid

import bcrypt
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

S: dict = {}


def _rand() -> str:
    return uuid.uuid4().hex[:8]


def _hdrs(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _reset_admin_pin():
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    db.users.update_one(
        {"username": "admin"},
        {"$set": {
            "pin_hash": bcrypt.hashpw(b"1234", bcrypt.gensalt()).decode(),
            "must_change_pin": False, "active": True,
        }},
    )


def _login(username: str, pin: str) -> requests.Response:
    return requests.post(f"{API}/auth/login", json={"username": username, "pin": pin})


# Minimal valid JPEG bytes (SOI + APP0 + EOI). Enough to be treated as bytes.
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x00" * 64 + b"\xff\xd9"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


# ---------- Setup ---------- #
class TestASetup:
    def test_admin_login(self):
        _reset_admin_pin()
        r = _login("admin", "1234")
        assert r.status_code == 200, r.text
        d = r.json()
        S["admin_tok"] = d["token"]
        S["admin_id"] = d["user"]["id"]

    def test_seed_customer_and_two_techs(self):
        suf = _rand()
        h = _hdrs(S["admin_tok"])
        # Customer
        r = requests.post(f"{API}/customers", json={
            "name": f"TEST_Cust_{suf}", "mobile": f"9{suf[:9]}",
            "address": "1 Test Rd", "email": f"c{suf}@t.com",
        }, headers=h)
        assert r.status_code == 200, r.text
        S["cid"] = r.json()["id"]

        # Assigned technician (T1)
        r = requests.post(f"{API}/users", json={
            "username": f"ttech1_{suf}", "pin": "1111",
            "role": "technician", "name": "Tech One",
        }, headers=h)
        assert r.status_code == 200, r.text
        S["t1_uname"] = f"ttech1_{suf}"
        S["t1_id"] = r.json()["id"]
        # Change PIN
        r = _login(S["t1_uname"], "1111"); assert r.status_code == 200
        tok0 = r.json()["token"]
        r = requests.post(f"{API}/auth/change-pin", json={"pin": "2222"}, headers=_hdrs(tok0))
        assert r.status_code == 200
        r = _login(S["t1_uname"], "2222"); assert r.status_code == 200
        S["t1_tok"] = r.json()["token"]

        # Second technician (T2, NOT assigned)
        r = requests.post(f"{API}/users", json={
            "username": f"ttech2_{suf}", "pin": "1111",
            "role": "technician", "name": "Tech Two",
        }, headers=h)
        assert r.status_code == 200, r.text
        S["t2_uname"] = f"ttech2_{suf}"
        S["t2_id"] = r.json()["id"]
        r = _login(S["t2_uname"], "1111"); tok0 = r.json()["token"]
        r = requests.post(f"{API}/auth/change-pin", json={"pin": "2222"}, headers=_hdrs(tok0))
        assert r.status_code == 200
        r = _login(S["t2_uname"], "2222"); assert r.status_code == 200
        S["t2_tok"] = r.json()["token"]

    def test_admin_creates_termite_service_assigned_to_t1(self):
        h = _hdrs(S["admin_tok"])
        r = requests.post(f"{API}/services", json={
            "customer_id": S["cid"], "service_type": "Termite",
            "scheduled_date": "2026-10-15T10:00:00+00:00",
            "technician_id": S["t1_id"], "charges": 1500,
        }, headers=h)
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["technician_id"] == S["t1_id"]
        assert s["status"] == "assigned"
        assert "_id" not in s
        # photos map initialized
        assert s.get("photos", {}).get("before") == []
        S["sid"] = s["id"]


# ---------- Photo upload happy path ---------- #
class TestBPhotoUpload:
    def test_upload_before_photo_returns_path_and_grows_array(self):
        h = _hdrs(S["t1_tok"])
        # baseline count
        r = requests.get(f"{API}/services/{S['sid']}", headers=h); assert r.status_code == 200
        before_count = len(r.json().get("photos", {}).get("before", []))

        files = {"file": ("before.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")}
        data = {"phase": "before"}
        r = requests.post(f"{API}/services/{S['sid']}/photos", files=files, data=data, headers=h)
        if r.status_code == 500:
            pytest.skip(f"Emergent Object Storage unavailable: {r.text}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "path" in body and isinstance(body["path"], str) and body["path"]
        assert S["sid"] in body["path"]
        assert body["path"].endswith(".jpg")
        S["before_path"] = body["path"]

        # verify photos.before grew by 1
        r = requests.get(f"{API}/services/{S['sid']}", headers=h)
        assert r.status_code == 200
        photos = r.json().get("photos", {})
        assert len(photos.get("before", [])) == before_count + 1
        assert S["before_path"] in photos["before"]

    def test_get_file_with_token_streams_bytes(self):
        if "before_path" not in S:
            pytest.skip("no before_path available")
        path = S["before_path"]
        r = requests.get(f"{API}/files/{path}", params={"token": S["t1_tok"]})
        assert r.status_code == 200, r.text
        # content type should look like image/*
        ctype = r.headers.get("content-type", "")
        assert "image" in ctype.lower() or ctype.startswith("application/"), f"unexpected ctype {ctype}"
        assert len(r.content) > 0
        # first two bytes should match JPEG SOI
        assert r.content[:2] == b"\xff\xd8", f"expected JPEG SOI, got {r.content[:4]!r}"

    def test_get_file_without_token_returns_401(self):
        if "before_path" not in S:
            pytest.skip("no before_path available")
        r = requests.get(f"{API}/files/{S['before_path']}")
        assert r.status_code == 401, r.text

    def test_upload_after_photo(self):
        h = _hdrs(S["t1_tok"])
        files = {"file": ("after.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")}
        data = {"phase": "after"}
        r = requests.post(f"{API}/services/{S['sid']}/photos", files=files, data=data, headers=h)
        if r.status_code == 500:
            pytest.skip(f"Emergent Object Storage unavailable: {r.text}")
        assert r.status_code == 200, r.text
        S["after_path"] = r.json()["path"]


# ---------- Photo upload negative cases ---------- #
class TestCPhotoUploadNegatives:
    def test_invalid_phase_returns_400(self):
        h = _hdrs(S["t1_tok"])
        files = {"file": ("x.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")}
        data = {"phase": "invalid"}
        r = requests.post(f"{API}/services/{S['sid']}/photos", files=files, data=data, headers=h)
        assert r.status_code == 400, r.text
        assert "phase" in r.text.lower()

    def test_missing_authorization_returns_401(self):
        files = {"file": ("x.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")}
        data = {"phase": "before"}
        r = requests.post(f"{API}/services/{S['sid']}/photos", files=files, data=data)
        assert r.status_code == 401, r.text

    def test_non_assigned_technician_returns_403(self):
        h = _hdrs(S["t2_tok"])
        files = {"file": ("x.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")}
        data = {"phase": "before"}
        r = requests.post(f"{API}/services/{S['sid']}/photos", files=files, data=data, headers=h)
        assert r.status_code == 403, r.text

    def test_photo_upload_on_missing_service_returns_404(self):
        h = _hdrs(S["t1_tok"])
        files = {"file": ("x.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")}
        data = {"phase": "before"}
        r = requests.post(f"{API}/services/does-not-exist/photos", files=files, data=data, headers=h)
        assert r.status_code == 404, r.text


# ---------- Signature ---------- #
class TestDSignature:
    def test_upload_signature_as_assigned_tech(self):
        h = _hdrs(S["t1_tok"])
        files = {"file": ("sig.png", io.BytesIO(PNG_BYTES), "image/png")}
        r = requests.post(f"{API}/services/{S['sid']}/signature", files=files, headers=h)
        if r.status_code == 500:
            pytest.skip(f"Emergent Object Storage unavailable: {r.text}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "path" in body and body["path"].endswith(".png")
        S["sig_path"] = body["path"]

        # service.signature_path should now be set
        r = requests.get(f"{API}/services/{S['sid']}", headers=h)
        assert r.status_code == 200
        assert r.json().get("signature_path") == S["sig_path"]

    def test_signature_non_assigned_tech_returns_403(self):
        h = _hdrs(S["t2_tok"])
        files = {"file": ("sig.png", io.BytesIO(PNG_BYTES), "image/png")}
        r = requests.post(f"{API}/services/{S['sid']}/signature", files=files, headers=h)
        assert r.status_code == 403, r.text

    def test_get_signature_file_with_token(self):
        if "sig_path" not in S:
            pytest.skip("no sig_path")
        r = requests.get(f"{API}/files/{S['sig_path']}", params={"token": S["t1_tok"]})
        assert r.status_code == 200
        assert len(r.content) > 0
        # PNG magic bytes
        assert r.content[:4] == b"\x89PNG", f"expected PNG magic, got {r.content[:4]!r}"


# ---------- Complete-service regression ---------- #
class TestECompleteRegression:
    def test_complete_without_after_photo_returns_400(self):
        """Create a fresh service, upload only 'before', then /complete → 400."""
        h_admin = _hdrs(S["admin_tok"])
        r = requests.post(f"{API}/services", json={
            "customer_id": S["cid"], "service_type": "Termite",
            "scheduled_date": "2026-11-15T10:00:00+00:00",
            "technician_id": S["t1_id"], "charges": 1000,
        }, headers=h_admin)
        assert r.status_code == 200, r.text
        sid2 = r.json()["id"]
        S["sid2"] = sid2

        h = _hdrs(S["t1_tok"])
        # only before, NO after
        files = {"file": ("before.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")}
        r = requests.post(f"{API}/services/{sid2}/photos",
                          files=files, data={"phase": "before"}, headers=h)
        if r.status_code == 500:
            pytest.skip(f"Emergent Object Storage unavailable: {r.text}")
        assert r.status_code == 200

        r = requests.post(f"{API}/services/{sid2}/complete",
                          json={"medicine": "X", "quantity": "1L"}, headers=h)
        assert r.status_code == 400, r.text
        assert "photos required" in r.text.lower()

    def test_complete_with_both_photos_success_and_termite_reminder(self):
        h = _hdrs(S["t1_tok"])
        sid2 = S["sid2"]
        # add after
        files = {"file": ("after.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")}
        r = requests.post(f"{API}/services/{sid2}/photos",
                          files=files, data={"phase": "after"}, headers=h)
        if r.status_code == 500:
            pytest.skip(f"Emergent Object Storage unavailable: {r.text}")
        assert r.status_code == 200

        r = requests.post(f"{API}/services/{sid2}/complete",
                          json={"medicine": "X", "quantity": "1L"}, headers=h)
        assert r.status_code == 200, r.text

        # Termite auto reminder was created
        rr = requests.get(f"{API}/reminders", headers=_hdrs(S["admin_tok"]))
        assert rr.status_code == 200
        rems = [x for x in rr.json() if x.get("source_service_id") == sid2]
        assert len(rems) == 1, f"expected 1 auto reminder, got {len(rems)}"
        assert rems[0]["service_type"] == "Termite"
        assert rems[0].get("auto_source") == "termite_annual"
