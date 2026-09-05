from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Form, Header, Query
from fastapi.responses import Response
from fastapi.concurrency import run_in_threadpool
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, logging, uuid, bcrypt, jwt, requests
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me-please")
JWT_ALG = "HS256"
JWT_EXP_HOURS = 24 * 30
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
APP_NAME = "pest-control-mgmt"

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI()
api = APIRouter(prefix="/api")
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("pest")

# ---------- Storage helpers ----------
_storage_key: Optional[str] = None
def _init_storage_sync():
    global _storage_key
    if _storage_key:
        return _storage_key
    if not EMERGENT_LLM_KEY:
        raise RuntimeError("EMERGENT_LLM_KEY missing")
    r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_LLM_KEY}, timeout=30)
    r.raise_for_status()
    _storage_key = r.json()["storage_key"]
    return _storage_key

def _put_object_sync(path: str, data: bytes, content_type: str):
    key = _init_storage_sync()
    r = requests.put(f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
    if r.status_code == 503:
        globals()["_storage_key"] = None
        key = _init_storage_sync()
        r = requests.put(f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
    r.raise_for_status()
    return r.json()

def _get_object_sync(path: str):
    key = _init_storage_sync()
    r = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if r.status_code == 503:
        globals()["_storage_key"] = None
        key = _init_storage_sync()
        r = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if r.status_code >= 400:
        raise HTTPException(404, "File not found")
    return r.content, r.headers.get("Content-Type", "application/octet-stream")

# ---------- Utility ----------
def now_utc():
    return datetime.now(timezone.utc)

def new_id():
    return str(uuid.uuid4())

def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()

def check_pin(pin: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pin.encode(), hashed.encode())
    except Exception:
        return False

def make_token(user_id: str, role: str) -> str:
    payload = {"sub": user_id, "role": role, "exp": now_utc() + timedelta(hours=JWT_EXP_HOURS)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

async def get_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        payload = jwt.decode(authorization.split(" ", 1)[1], JWT_SECRET, algorithms=[JWT_ALG])
    except Exception:
        raise HTTPException(401, "Invalid token")
    u = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "pin_hash": 0})
    if not u or not u.get("active", True):
        raise HTTPException(401, "User not found/inactive")
    return u

def require_roles(*roles):
    async def dep(user=Depends(get_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "Forbidden")
        return user
    return dep

# ---------- Models ----------
class LoginIn(BaseModel):
    username: str
    pin: str

class CreateUserIn(BaseModel):
    username: str
    name: str
    role: Literal["admin", "manager", "technician"]
    pin: str
    phone: Optional[str] = None

class UpdateUserIn(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    active: Optional[bool] = None

class SetPinIn(BaseModel):
    pin: str

class CustomerIn(BaseModel):
    name: str
    mobile: str
    alt_mobile: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    notes: Optional[str] = None

class ServiceTypeIn(BaseModel):
    name: str

class ServiceIn(BaseModel):
    customer_id: str
    service_type: str
    scheduled_date: str  # ISO datetime
    technician_id: Optional[str] = None
    charges: Optional[float] = 0
    payment_status: Optional[str] = "unpaid"
    instructions: Optional[str] = None
    admin_notes: Optional[str] = None

class ServiceUpdateIn(BaseModel):
    customer_id: Optional[str] = None
    service_type: Optional[str] = None
    scheduled_date: Optional[str] = None
    technician_id: Optional[str] = None
    charges: Optional[float] = None
    payment_status: Optional[str] = None
    instructions: Optional[str] = None
    admin_notes: Optional[str] = None
    status: Optional[str] = None
    medicine: Optional[str] = None
    quantity: Optional[str] = None
    technician_notes: Optional[str] = None

class TechCompleteIn(BaseModel):
    medicine: Optional[str] = None
    quantity: Optional[str] = None
    technician_notes: Optional[str] = None

class AMCIn(BaseModel):
    customer_id: str
    service_type: str
    start_date: str
    end_date: str
    frequency: Literal["daily", "fortnightly", "monthly", "quarterly", "custom"]
    contract_amount: Optional[float] = 0
    notes: Optional[str] = None
    custom_interval_days: Optional[int] = None

class ReminderIn(BaseModel):
    customer_id: str
    service_type: str
    due_date: str
    notes: Optional[str] = None
    reminder_period_months: Optional[int] = None

class FeedbackIn(BaseModel):
    service_id: str
    rating: int
    comment: Optional[str] = None
    customer_name: Optional[str] = None

class SettingsIn(BaseModel):
    google_review_url: Optional[str] = None
    whatsapp_template: Optional[str] = None

async def create_termite_reminder_if_needed(user, service):
    """After a Termite service is completed, create an Admin reminder 7 days before the same calendar date one year later.
    Prevent duplicates by checking existing reminders for the same customer/service_type/due_date."""
    if (service.get("service_type") or "").strip().lower() != "termite":
        return
    completed_at = service.get("completed_at") or now_utc().isoformat()
    try:
        cd = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
    except Exception:
        cd = now_utc()
    due = cd + relativedelta(years=1) - timedelta(days=7)
    due_iso = due.isoformat()
    # Prevent duplicates: any reminder for this customer + Termite within +/- 2 days of computed due
    win_start = (due - timedelta(days=2)).isoformat()
    win_end = (due + timedelta(days=2)).isoformat()
    exists = await db.reminders.find_one({
        "customer_id": service["customer_id"], "service_type": "Termite",
        "due_date": {"$gte": win_start, "$lte": win_end},
    })
    if exists:
        return
    r = {
        "id": new_id(), "customer_id": service["customer_id"], "service_type": "Termite",
        "due_date": due_iso, "notes": "Annual termite follow-up (auto-created)",
        "reminder_period_months": 12, "status": "upcoming",
        "auto_source": "termite_annual", "source_service_id": service["id"],
        "created_at": now_utc().isoformat(),
    }
    await db.reminders.insert_one(r)
    await audit(user, "reminder", r["id"], "auto_create", {"source": "termite_annual"})

# ---------- Audit ----------
async def audit(user, entity, entity_id, action, changes=None):
    await db.audit_logs.insert_one({
        "id": new_id(), "user_id": user["id"], "user_name": user.get("name"),
        "entity": entity, "entity_id": entity_id, "action": action,
        "changes": changes or {}, "at": now_utc().isoformat()
    })

# ---------- Auth ----------
@api.post("/auth/login")
async def login(inp: LoginIn):
    u = await db.users.find_one({"username": inp.username.lower().strip()})
    if not u or not u.get("active", True):
        raise HTTPException(401, "Invalid credentials")
    if not check_pin(inp.pin, u["pin_hash"]):
        raise HTTPException(401, "Invalid credentials")
    token = make_token(u["id"], u["role"])
    return {
        "token": token,
        "user": {"id": u["id"], "username": u["username"], "name": u["name"], "role": u["role"],
                 "must_change_pin": u.get("must_change_pin", False)}
    }

@api.get("/auth/me")
async def me(user=Depends(get_user)):
    return user

@api.post("/auth/change-pin")
async def change_pin(inp: SetPinIn, user=Depends(get_user)):
    if not inp.pin.isdigit() or len(inp.pin) != 4:
        raise HTTPException(400, "PIN must be 4 digits")
    await db.users.update_one({"id": user["id"]}, {"$set": {"pin_hash": hash_pin(inp.pin), "must_change_pin": False}})
    return {"ok": True}

# ---------- Users (Admin) ----------
@api.get("/users")
async def list_users(role: Optional[str] = None, user=Depends(get_user)):
    if user["role"] not in ("admin", "manager"):
        raise HTTPException(403, "Forbidden")
    # Manager cannot see other managers/admins management-level, but can list technicians for assignment
    q = {}
    if role:
        q["role"] = role
    if user["role"] == "manager":
        q["role"] = "technician"
    users = await db.users.find(q, {"_id": 0, "pin_hash": 0}).to_list(500)
    return users

@api.post("/users")
async def create_user(inp: CreateUserIn, user=Depends(require_roles("admin"))):
    if not inp.pin.isdigit() or len(inp.pin) != 4:
        raise HTTPException(400, "PIN must be 4 digits")
    if inp.role == "admin":
        raise HTTPException(400, "Cannot create another admin")
    exists = await db.users.find_one({"username": inp.username.lower().strip()})
    if exists:
        raise HTTPException(400, "Username already exists")
    u = {
        "id": new_id(), "username": inp.username.lower().strip(), "name": inp.name,
        "role": inp.role, "phone": inp.phone, "pin_hash": hash_pin(inp.pin),
        "active": True, "must_change_pin": True, "created_at": now_utc().isoformat()
    }
    await db.users.insert_one(u)
    await audit(user, "user", u["id"], "create", {"role": inp.role, "username": u["username"]})
    return {"id": u["id"]}

@api.patch("/users/{uid}")
async def update_user(uid: str, inp: UpdateUserIn, user=Depends(require_roles("admin"))):
    upd = {k: v for k, v in inp.dict().items() if v is not None}
    if not upd:
        return {"ok": True}
    await db.users.update_one({"id": uid}, {"$set": upd})
    await audit(user, "user", uid, "update", upd)
    return {"ok": True}

@api.post("/users/{uid}/reset-pin")
async def reset_pin(uid: str, inp: SetPinIn, user=Depends(require_roles("admin"))):
    if not inp.pin.isdigit() or len(inp.pin) != 4:
        raise HTTPException(400, "PIN must be 4 digits")
    await db.users.update_one({"id": uid}, {"$set": {"pin_hash": hash_pin(inp.pin), "must_change_pin": True}})
    await audit(user, "user", uid, "reset_pin")
    return {"ok": True}

# ---------- Customers ----------
@api.get("/customers")
async def list_customers(q: Optional[str] = None, user=Depends(get_user)):
    if user["role"] == "technician":
        raise HTTPException(403, "Forbidden")
    query = {}
    if q:
        query = {"$or": [{"name": {"$regex": q, "$options": "i"}}, {"mobile": {"$regex": q}}]}
    cs = await db.customers.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return cs

@api.post("/customers")
async def create_customer(inp: CustomerIn, user=Depends(require_roles("admin", "manager"))):
    c = {**inp.dict(), "id": new_id(), "created_at": now_utc().isoformat(), "created_by": user["id"]}
    await db.customers.insert_one(c)
    c.pop("_id", None)
    await audit(user, "customer", c["id"], "create")
    return c

@api.get("/customers/{cid}")
async def get_customer(cid: str, user=Depends(get_user)):
    c = await db.customers.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Not found")
    services = await db.services.find({"customer_id": cid}, {"_id": 0}).sort("scheduled_date", -1).to_list(500)
    if user["role"] == "technician":
        services = [s for s in services if s.get("technician_id") == user["id"]]
    # Strip financials for non-admin
    if user["role"] != "admin":
        for s in services:
            s.pop("charges", None)
    return {"customer": c, "services": services}

@api.patch("/customers/{cid}")
async def update_customer(cid: str, inp: CustomerIn, user=Depends(require_roles("admin", "manager"))):
    await db.customers.update_one({"id": cid}, {"$set": inp.dict()})
    await audit(user, "customer", cid, "update")
    return {"ok": True}

# ---------- Service Types ----------
@api.get("/service-types")
async def list_service_types(user=Depends(get_user)):
    types = await db.service_types.find({}, {"_id": 0}).to_list(200)
    return types

@api.post("/service-types")
async def create_service_type(inp: ServiceTypeIn, user=Depends(require_roles("admin"))):
    exists = await db.service_types.find_one({"name": inp.name})
    if exists:
        raise HTTPException(400, "Already exists")
    st = {"id": new_id(), "name": inp.name}
    await db.service_types.insert_one(st)
    return {"id": st["id"]}

# ---------- Services ----------
def strip_financials(s, role):
    if role != "admin":
        s.pop("charges", None)
    return s

@api.get("/services")
async def list_services(
    status: Optional[str] = None,
    technician_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    service_type: Optional[str] = None,
    q: Optional[str] = None,
    user=Depends(get_user),
):
    query = {}
    if user["role"] == "technician":
        query["technician_id"] = user["id"]
    elif technician_id:
        query["technician_id"] = technician_id
    if status:
        query["status"] = status
    if customer_id:
        query["customer_id"] = customer_id
    if service_type:
        query["service_type"] = service_type
    if date_from or date_to:
        rng = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to
        query["scheduled_date"] = rng
    services = await db.services.find(query, {"_id": 0}).sort("scheduled_date", 1).to_list(1000)
    # Attach customer summary
    cids = list({s["customer_id"] for s in services})
    customers = {c["id"]: c async for c in db.customers.find({"id": {"$in": cids}}, {"_id": 0})}
    for s in services:
        c = customers.get(s["customer_id"], {})
        s["customer_name"] = c.get("name")
        s["customer_mobile"] = c.get("mobile")
        s["customer_address"] = c.get("address")
        strip_financials(s, user["role"])
    if q:
        ql = q.lower()
        services = [s for s in services if ql in (s.get("customer_name") or "").lower() or ql in (s.get("customer_mobile") or "")]
    return services

@api.post("/services")
async def create_service(inp: ServiceIn, user=Depends(require_roles("admin", "manager"))):
    c = await db.customers.find_one({"id": inp.customer_id})
    if not c:
        raise HTTPException(400, "Customer not found")
    s = {
        **inp.dict(), "id": new_id(),
        "status": "assigned" if inp.technician_id else "pending",
        "created_at": now_utc().isoformat(), "created_by": user["id"],
        "photos": {"before": [], "during": [], "after": []},
        "medicine": None, "quantity": None, "technician_notes": None,
        "completed_at": None,
    }
    if user["role"] != "admin":
        s["charges"] = 0
    await db.services.insert_one(s)
    s.pop("_id", None)
    await audit(user, "service", s["id"], "create")
    return s

@api.get("/services/{sid}")
async def get_service(sid: str, user=Depends(get_user)):
    s = await db.services.find_one({"id": sid}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Not found")
    if user["role"] == "technician" and s.get("technician_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    c = await db.customers.find_one({"id": s["customer_id"]}, {"_id": 0})
    s["customer"] = c
    strip_financials(s, user["role"])
    return s

@api.patch("/services/{sid}")
async def update_service(sid: str, inp: ServiceUpdateIn, user=Depends(get_user)):
    s = await db.services.find_one({"id": sid})
    if not s:
        raise HTTPException(404, "Not found")
    upd = {k: v for k, v in inp.dict().items() if v is not None}
    if user["role"] == "technician":
        # Technician limited to own service progress fields
        if s.get("technician_id") != user["id"]:
            raise HTTPException(403, "Forbidden")
        allowed = {"status", "medicine", "quantity", "technician_notes", "payment_status"}
        upd = {k: v for k, v in upd.items() if k in allowed}
        if not upd:
            raise HTTPException(400, "Nothing to update")
    else:
        if s.get("status") == "completed" and user["role"] != "admin":
            raise HTTPException(400, "Service completed and locked")
        if user["role"] == "manager":
            upd.pop("charges", None)
        # Technician change
        if "technician_id" in upd and upd["technician_id"] != s.get("technician_id"):
            # Auto-set status assigned when adding tech to pending
            if s.get("status") == "pending" and upd["technician_id"]:
                upd["status"] = upd.get("status", "assigned")
    if "status" in upd and upd["status"] == "completed":
        upd["completed_at"] = now_utc().isoformat()
    await db.services.update_one({"id": sid}, {"$set": upd})
    if upd.get("status") == "completed":
        after = await db.services.find_one({"id": sid})
        await create_termite_reminder_if_needed(user, after)
    await audit(user, "service", sid, "update", upd)
    return {"ok": True}

@api.post("/services/{sid}/complete")
async def complete_service(sid: str, inp: TechCompleteIn, user=Depends(get_user)):
    s = await db.services.find_one({"id": sid})
    if not s:
        raise HTTPException(404, "Not found")
    if user["role"] == "technician" and s.get("technician_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    photos = s.get("photos", {})
    if not photos.get("before") or not photos.get("after"):
        raise HTTPException(400, "Before and After photos required")
    upd = {**{k: v for k, v in inp.dict().items() if v is not None},
           "status": "completed", "completed_at": now_utc().isoformat()}
    await db.services.update_one({"id": sid}, {"$set": upd})
    after = await db.services.find_one({"id": sid})
    await create_termite_reminder_if_needed(user, after)
    await db.feedback_requests.insert_one({
        "id": new_id(), "service_id": sid, "customer_id": s["customer_id"],
        "status": "pending", "created_at": now_utc().isoformat()
    })
    await audit(user, "service", sid, "complete")
    return {"ok": True}

@api.post("/services/{sid}/signature")
async def upload_signature(sid: str, file: UploadFile = File(...), user=Depends(get_user)):
    s = await db.services.find_one({"id": sid})
    if not s:
        raise HTTPException(404, "Not found")
    if user["role"] == "technician" and s.get("technician_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    ext = (file.filename or "sig.png").split(".")[-1].lower() or "png"
    path = f"{APP_NAME}/services/{sid}/signature/{new_id()}.{ext}"
    data = await file.read()
    await run_in_threadpool(_put_object_sync, path, data, file.content_type or "image/png")
    await db.services.update_one({"id": sid}, {"$set": {"signature_path": path, "signature_at": now_utc().isoformat()}})
    await audit(user, "service", sid, "signature")
    return {"path": path}

# ---------- Photos ----------
@api.post("/services/{sid}/photos")
async def upload_photo(sid: str, phase: str = Form(...), file: UploadFile = File(...), user=Depends(get_user)):
    if phase not in ("before", "during", "after"):
        raise HTTPException(400, "Invalid phase")
    s = await db.services.find_one({"id": sid})
    if not s:
        raise HTTPException(404, "Not found")
    if user["role"] == "technician" and s.get("technician_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    ext = (file.filename or "img.jpg").split(".")[-1].lower() or "jpg"
    path = f"{APP_NAME}/services/{sid}/{phase}/{new_id()}.{ext}"
    data = await file.read()
    await run_in_threadpool(_put_object_sync, path, data, file.content_type or "image/jpeg")
    await db.services.update_one({"id": sid}, {"$push": {f"photos.{phase}": path}})
    await audit(user, "service", sid, f"photo_{phase}")
    return {"path": path}

@api.get("/files/{path:path}")
async def get_file(path: str, token: Optional[str] = Query(None), authorization: Optional[str] = Header(None)):
    # Accept token via query for web <img> tags
    tok = None
    if authorization and authorization.startswith("Bearer "):
        tok = authorization.split(" ", 1)[1]
    elif token:
        tok = token
    if not tok:
        raise HTTPException(401, "Missing token")
    try:
        jwt.decode(tok, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception:
        raise HTTPException(401, "Invalid token")
    content, ctype = await run_in_threadpool(_get_object_sync, path)
    return Response(content=content, media_type=ctype)

# ---------- AMC ----------
def generate_schedule(start: datetime, end: datetime, freq: str, custom_days: Optional[int]) -> List[datetime]:
    dates = []
    cur = start
    if freq == "daily":
        while cur <= end:
            dates.append(cur); cur += timedelta(days=1)
    elif freq == "fortnightly":
        while cur <= end:
            dates.append(cur); cur += timedelta(days=14)
    elif freq == "monthly":
        while cur <= end:
            dates.append(cur); cur += relativedelta(months=1)
    elif freq == "quarterly":
        while cur <= end:
            dates.append(cur); cur += relativedelta(months=3)
    elif freq == "custom":
        interval = max(1, custom_days or 30)
        while cur <= end:
            dates.append(cur); cur += timedelta(days=interval)
    return dates

@api.get("/amc")
async def list_amc(user=Depends(get_user)):
    if user["role"] == "technician":
        raise HTTPException(403, "Forbidden")
    amcs = await db.contracts.find({}, {"_id": 0}).sort("start_date", -1).to_list(500)
    cids = list({a["customer_id"] for a in amcs})
    customers = {c["id"]: c async for c in db.customers.find({"id": {"$in": cids}}, {"_id": 0})}
    for a in amcs:
        c = customers.get(a["customer_id"], {})
        a["customer_name"] = c.get("name")
        a["customer_mobile"] = c.get("mobile")
        if user["role"] != "admin":
            a.pop("contract_amount", None)
    return amcs

@api.post("/amc")
async def create_amc(inp: AMCIn, user=Depends(require_roles("admin", "manager"))):
    c = await db.customers.find_one({"id": inp.customer_id})
    if not c:
        raise HTTPException(400, "Customer not found")
    start = datetime.fromisoformat(inp.start_date.replace("Z", "+00:00"))
    end = datetime.fromisoformat(inp.end_date.replace("Z", "+00:00"))
    if end < start:
        raise HTTPException(400, "End date must be after start")
    amc = {**inp.dict(), "id": new_id(), "created_at": now_utc().isoformat(), "created_by": user["id"]}
    if user["role"] != "admin":
        amc["contract_amount"] = 0
    await db.contracts.insert_one(amc)
    # Generate scheduled services
    dates = generate_schedule(start, end, inp.frequency, inp.custom_interval_days)
    for d in dates:
        svc = {
            "id": new_id(), "customer_id": inp.customer_id, "service_type": inp.service_type,
            "scheduled_date": d.isoformat(), "technician_id": None, "charges": 0,
            "payment_status": "amc", "instructions": inp.notes, "status": "pending",
            "amc_id": amc["id"], "created_at": now_utc().isoformat(), "created_by": user["id"],
            "photos": {"before": [], "during": [], "after": []},
            "medicine": None, "quantity": None, "technician_notes": None, "completed_at": None,
        }
        await db.services.insert_one(svc)
    await audit(user, "amc", amc["id"], "create", {"generated": len(dates)})
    amc.pop("_id", None)
    return {**amc, "generated": len(dates)}

@api.get("/amc/{aid}")
async def get_amc(aid: str, user=Depends(get_user)):
    if user["role"] == "technician":
        raise HTTPException(403, "Forbidden")
    a = await db.contracts.find_one({"id": aid}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Not found")
    c = await db.customers.find_one({"id": a["customer_id"]}, {"_id": 0})
    services = await db.services.find({"amc_id": aid}, {"_id": 0}).sort("scheduled_date", 1).to_list(1000)
    if user["role"] != "admin":
        a.pop("contract_amount", None)
        for s in services: s.pop("charges", None)
    return {"amc": a, "customer": c, "services": services}

# ---------- Reminders ----------
@api.get("/reminders")
async def list_reminders(user=Depends(get_user)):
    if user["role"] == "technician":
        raise HTTPException(403, "Forbidden")
    rs = await db.reminders.find({}, {"_id": 0}).sort("due_date", 1).to_list(500)
    cids = list({r["customer_id"] for r in rs})
    customers = {c["id"]: c async for c in db.customers.find({"id": {"$in": cids}}, {"_id": 0})}
    now_iso = now_utc().isoformat()
    for r in rs:
        c = customers.get(r["customer_id"], {})
        r["customer_name"] = c.get("name")
        r["customer_mobile"] = c.get("mobile")
        if r.get("status") == "completed":
            r["computed"] = "completed"
        elif r["due_date"] < now_iso:
            r["computed"] = "overdue"
        elif r["due_date"] < (now_utc() + timedelta(days=7)).isoformat():
            r["computed"] = "due"
        else:
            r["computed"] = "upcoming"
    return rs

@api.post("/reminders")
async def create_reminder(inp: ReminderIn, user=Depends(require_roles("admin", "manager"))):
    r = {**inp.dict(), "id": new_id(), "status": "upcoming", "created_at": now_utc().isoformat()}
    await db.reminders.insert_one(r)
    r.pop("_id", None)
    await audit(user, "reminder", r["id"], "create")
    return r

@api.patch("/reminders/{rid}")
async def update_reminder(rid: str, inp: ReminderIn, user=Depends(require_roles("admin", "manager"))):
    await db.reminders.update_one({"id": rid}, {"$set": inp.dict()})
    return {"ok": True}

@api.post("/reminders/{rid}/complete")
async def complete_reminder(rid: str, user=Depends(require_roles("admin", "manager"))):
    await db.reminders.update_one({"id": rid}, {"$set": {"status": "completed", "completed_at": now_utc().isoformat()}})
    return {"ok": True}

# ---------- Feedback ----------
@api.get("/feedback")
async def list_feedback(user=Depends(require_roles("admin", "manager"))):
    fs = await db.feedback.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return fs

@api.post("/feedback")
async def submit_feedback(inp: FeedbackIn):
    # Public endpoint via share link (no auth) - customer submits feedback
    fb = {**inp.dict(), "id": new_id(), "created_at": now_utc().isoformat(), "approved": False}
    await db.feedback.insert_one(fb)
    fb.pop("_id", None)
    return fb

@api.post("/feedback/{fid}/approve")
async def approve_feedback(fid: str, user=Depends(require_roles("admin"))):
    await db.feedback.update_one({"id": fid}, {"$set": {"approved": True}})
    return {"ok": True}

# ---------- Settings ----------
@api.get("/settings")
async def get_settings(user=Depends(get_user)):
    s = await db.settings.find_one({"id": "app"}, {"_id": 0}) or {"id": "app", "google_review_url": "", "whatsapp_template": ""}
    return s

@api.patch("/settings")
async def update_settings(inp: SettingsIn, user=Depends(require_roles("admin"))):
    upd = {k: v for k, v in inp.dict().items() if v is not None}
    await db.settings.update_one({"id": "app"}, {"$set": {"id": "app", **upd}}, upsert=True)
    return {"ok": True}

# ---------- Dashboards ----------
@api.get("/dashboard/admin")
async def admin_dashboard(user=Depends(require_roles("admin"))):
    now = now_utc()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = (month_start + relativedelta(months=1))

    async def cnt(q): return await db.services.count_documents(q)
    today = await cnt({"scheduled_date": {"$gte": today_start.isoformat(), "$lt": today_end.isoformat()}})
    pending = await cnt({"status": {"$in": ["pending", "assigned"]}})
    completed_today = await cnt({"status": "completed", "completed_at": {"$gte": today_start.isoformat()}})
    month_pending = await cnt({"status": {"$in": ["pending", "assigned", "in_progress"]},
                               "scheduled_date": {"$gte": month_start.isoformat(), "$lt": month_end.isoformat()}})
    amc_due_month = await cnt({"amc_id": {"$ne": None}, "status": {"$in": ["pending", "assigned"]},
                               "scheduled_date": {"$gte": month_start.isoformat(), "$lt": month_end.isoformat()}})
    reminders_upcoming = await db.reminders.count_documents({"due_date": {"$gte": now.isoformat()}, "status": {"$ne": "completed"}})
    reminders_overdue = await db.reminders.count_documents({"due_date": {"$lt": now.isoformat()}, "status": {"$ne": "completed"}})

    # Amounts (admin only)
    today_amt = 0.0; month_amt = 0.0
    async for s in db.services.find({"status": "completed", "completed_at": {"$gte": today_start.isoformat()}}, {"charges": 1, "_id": 0}):
        today_amt += float(s.get("charges") or 0)
    async for s in db.services.find({"status": "completed", "completed_at": {"$gte": month_start.isoformat(), "$lt": month_end.isoformat()}}, {"charges": 1, "_id": 0}):
        month_amt += float(s.get("charges") or 0)

    return {
        "today_services": today, "pending_services": pending, "completed_today": completed_today,
        "month_pending": month_pending, "amc_due_this_month": amc_due_month,
        "reminders_upcoming": reminders_upcoming, "reminders_overdue": reminders_overdue,
        "today_amount": today_amt, "month_amount": month_amt
    }

@api.get("/dashboard/manager")
async def manager_dashboard(user=Depends(require_roles("manager", "admin"))):
    pending_payments = await db.services.count_documents({"status": "completed", "payment_status": {"$in": ["unpaid", "pending"]}})
    pending = await db.services.count_documents({"status": {"$in": ["pending", "assigned"]}})
    recent = await db.services.find({"status": "completed"}, {"_id": 0}).sort("completed_at", -1).limit(10).to_list(10)
    for r in recent: r.pop("charges", None)
    upcoming_reminders = await db.reminders.count_documents({"status": {"$ne": "completed"}})
    return {"pending_payments": pending_payments, "pending_services": pending,
            "upcoming_reminders": upcoming_reminders, "recent_completed": recent}

@api.get("/dashboard/technician")
async def technician_dashboard(user=Depends(require_roles("technician"))):
    now = now_utc()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    today = await db.services.count_documents({"technician_id": user["id"],
        "scheduled_date": {"$gte": today_start.isoformat(), "$lt": today_end.isoformat()},
        "status": {"$in": ["assigned", "in_progress"]}})
    upcoming = await db.services.count_documents({"technician_id": user["id"],
        "scheduled_date": {"$gte": today_end.isoformat()}, "status": {"$in": ["assigned", "pending"]}})
    completed = await db.services.count_documents({"technician_id": user["id"], "status": "completed"})
    return {"today": today, "upcoming": upcoming, "completed": completed}

# ---------- Reports (Admin) ----------
@api.get("/reports/summary")
async def reports_summary(user=Depends(require_roles("admin"))):
    now = now_utc()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total_revenue = 0.0
    by_type: dict = {}
    async for s in db.services.find({"status": "completed"}, {"charges": 1, "service_type": 1, "_id": 0}):
        c = float(s.get("charges") or 0)
        total_revenue += c
        by_type[s.get("service_type", "Other")] = by_type.get(s.get("service_type", "Other"), 0) + c
    month_revenue = 0.0
    async for s in db.services.find({"status": "completed", "completed_at": {"$gte": month_start.isoformat()}}, {"charges": 1, "_id": 0}):
        month_revenue += float(s.get("charges") or 0)
    tech_counts = []
    async for u in db.users.find({"role": "technician"}, {"_id": 0, "pin_hash": 0}):
        c = await db.services.count_documents({"technician_id": u["id"], "status": "completed"})
        tech_counts.append({"id": u["id"], "name": u["name"], "completed": c})
    return {"total_revenue": total_revenue, "month_revenue": month_revenue,
            "by_service_type": by_type, "technicians": tech_counts}

# ---------- Startup ----------
@app.on_event("startup")
async def startup():
    # Seed admin
    admin = await db.users.find_one({"username": "admin"})
    if not admin:
        await db.users.insert_one({
            "id": new_id(), "username": "admin", "name": "Owner", "role": "admin",
            "phone": None, "pin_hash": hash_pin("1234"), "active": True,
            "must_change_pin": True, "created_at": now_utc().isoformat()
        })
        log.info("Seeded admin/1234")
    # Seed default service types
    defaults = ["Cockroach", "Termite", "Rodent", "Mosquito", "General Pest Control"]
    for n in defaults:
        if not await db.service_types.find_one({"name": n}):
            await db.service_types.insert_one({"id": new_id(), "name": n})
    # Settings
    if not await db.settings.find_one({"id": "app"}):
        await db.settings.insert_one({"id": "app", "google_review_url": "",
            "whatsapp_template": "Hi {name}, please share your feedback about our pest control service: {link}"})
    # Init object storage
    try:
        await run_in_threadpool(_init_storage_sync)
        log.info("Storage initialized")
    except Exception as e:
        log.warning(f"Storage init deferred: {e}")

@app.on_event("shutdown")
async def shutdown():
    client.close()

app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
