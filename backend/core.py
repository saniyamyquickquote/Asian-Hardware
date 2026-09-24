import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

import bcrypt
import jwt
from fastapi import HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, ReturnDocument

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
IST = ZoneInfo("Asia/Kolkata")
SECRET = os.environ["JWT_SECRET"]


def now():
    return datetime.now(timezone.utc).isoformat()


def fy():
    dt = datetime.now(IST)
    start = dt.year if dt.month >= 4 else dt.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def uid():
    return str(uuid.uuid4())


def money(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def as_float(value):
    return float(money(value))


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())


def authorize(principal, action):
    """Single-org owner access: authenticated owner is the only allowed principal."""
    if not principal or principal.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    return principal


async def require_admin(request: Request):
    token = request.cookies.get("ah_session")
    if not token:
        raise HTTPException(status_code=401, detail="Please sign in")
    try:
        claims = jwt.decode(token, SECRET, algorithms=["HS256"])
        user = await db.users.find_one({"id": claims["sub"]}, {"_id": 0})
        if not user or user.get("sessionVersion", 0) != claims.get("version", 0):
            raise HTTPException(status_code=401, detail="Session expired")
        return authorize(user, "admin:access")
    except (jwt.PyJWTError, KeyError):
        raise HTTPException(status_code=401, detail="Session expired")


def issue_token(user):
    expiry = datetime.now(timezone.utc) + timedelta(hours=12)
    return jwt.encode({"sub": user["id"], "version": user.get("sessionVersion", 0), "exp": expiry}, SECRET, algorithm="HS256")


async def next_number(kind):
    prefix, key = ("AH", "nextBillNumber") if kind == "bill" else ("QT", "nextQuotationNumber")
    setting = await db.settings.find_one_and_update({"id": "default"}, {"$inc": {key: 1}}, return_document=ReturnDocument.BEFORE, projection={"_id": 0})
    return f"{prefix}/{fy()}/{setting[key]:05d}"


async def bootstrap():
    await db.users.create_index("username", unique=True)
    await db.products.create_index("id", unique=True)
    await db.products.create_index("sku", unique=True)
    await db.bills.create_index("number", unique=True)
    await db.bills.create_index("idempotencyKey", unique=True, sparse=True)
    await db.bills.create_index([("date", -1)])
    await db.bills.create_index([("customerId", 1), ("date", -1)])
    await db.bills.create_index([("status", 1), ("paymentMode", 1), ("date", -1)])
    await db.quotations.create_index("number", unique=True)
    await db.customers.create_index("phone", unique=True, sparse=True)
    await db.settings.update_one({"id": "default"}, {"$setOnInsert": {
        "id": "default", "storeName": "Asian Hardware and Paints", "storeNameMarathi": "एशियन हार्डवेअर अँड पेन्ट्स",
        "address1": "Ambad Satpur Link Road, Sanjeev Nagar, Nashik, Maharashtra 422010",
        "address2": "Ambad, Nashik, Maharashtra", "phone1": "84118 80222", "phone2": "82089 68883",
        "gstin": "27CHXPC0935Q2ZK", "printFormat": "thermal", "nextBillNumber": 1,
        "nextQuotationNumber": 1, "quotationValidity": 7,
        "quotationTerms": "Prices valid for 7 days. Transportation extra. Subject to stock availability.",
        "footerMessage": "Thank you for shopping with us! Visit again.", "financialYear": fy(),
    }}, upsert=True)
    if not await db.users.find_one({"username": "admin"}):
        await db.users.insert_one({"id": uid(), "username": "admin", "name": "Store Owner", "role": "admin",
                                   "passwordHash": hash_password("asian2019"), "sessionVersion": 0, "createdAt": now()})
    if await db.products.count_documents({}) == 0:
        path = Path(__file__).parent / "data" / "products.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        docs = []
        for index, row in enumerate(rows, 1):
            docs.append({"id": uid(), "name": row["name"], "category": row["category"],
                         "sku": f"AH-{index:05d}", "originalCode": row.get("originalCode"),
                         "salePrice": row["salePrice"], "purchasePrice": 0, "wholesalePrice": None,
                         "gstRate": 18, "currentStock": 0, "minStockLevel": 5, "reorderQty": 10,
                         "unit": "Piece", "location": "Store 1", "isActive": True,
                         "hsnCode": "", "brand": "", "barcode": "", "subCategory": "",
                         "description": "", "notes": "", "imageUrl": "", "stockCounted": False,
                         "createdAt": now(), "updatedAt": now()})
        await db.products.insert_many(docs)