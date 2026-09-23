import csv
import io
import re
from datetime import datetime, timezone

from bson.binary import Binary
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from core import as_float, db, now, require_admin, uid
from seed_from_pdf import category as infer_category

router = APIRouter(tags=["inventory"])
PRODUCT_FIELDS = {"name", "category", "subCategory", "sku", "hsnCode", "brand", "unit", "purchasePrice", "salePrice", "wholesalePrice", "gstRate", "currentStock", "minStockLevel", "reorderQty", "location", "description", "imageUrl", "isActive", "barcode", "notes"}
SETTING_FIELDS = {"storeName", "storeNameMarathi", "address1", "address2", "phone1", "phone2", "gstin", "email", "printFormat", "quotationValidity", "quotationTerms", "footerMessage"}


class ProductInput(BaseModel):
    name: str = Field(min_length=1)
    category: str = "General & Misc"
    subCategory: str = ""
    sku: str | None = None
    hsnCode: str = ""
    brand: str = ""
    unit: str = "Piece"
    purchasePrice: float = Field(default=0, ge=0)
    salePrice: float = Field(default=0, ge=0)
    wholesalePrice: float | None = Field(default=None, ge=0)
    gstRate: float = Field(default=18, ge=0, le=28)
    currentStock: int = 0
    minStockLevel: int = Field(default=5, ge=0)
    reorderQty: int = Field(default=10, ge=0)
    location: str = "Store 1"
    description: str = ""
    imageUrl: str = ""
    isActive: bool = True
    barcode: str = ""
    notes: str = ""


class CustomerInput(BaseModel):
    name: str = Field(min_length=1)
    phone: str = ""
    address: str = ""
    gstin: str = ""
    email: str = ""
    creditLimit: float = Field(default=0, ge=0)
    notes: str = ""


class PaymentInput(BaseModel):
    amount: float = Field(gt=0)
    mode: str = "Cash"
    reference: str = ""
    notes: str = ""


class AdjustmentInput(BaseModel):
    newQty: int
    reason: str
    notes: str = ""


class InquiryInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=8, max_length=20)
    message: str = Field(min_length=5, max_length=2000)


@router.get("/products")
async def products(q: str = "", category: str = "", stock: str = "all", page: int = Query(1, ge=1), perPage: int = Query(25, ge=1, le=1000), all: bool = False, user=Depends(require_admin)):
    query = {"isActive": True}
    if q.strip():
        safe = re.escape(q.strip())
        query["$or"] = [{"name": {"$regex": safe, "$options": "i"}}, {"sku": {"$regex": safe, "$options": "i"}}, {"barcode": {"$regex": safe, "$options": "i"}}]
    if category:
        query["category"] = category
    if stock == "out":
        query["currentStock"] = {"$lte": 0}
    elif stock == "low":
        query["currentStock"] = {"$gt": 0, "$lte": 5}
    elif stock == "available":
        query["currentStock"] = {"$gt": 0}
    total = await db.products.count_documents(query)
    cursor = db.products.find(query, {"_id": 0}).sort("name", 1)
    if not all:
        cursor = cursor.skip((page - 1) * perPage).limit(perPage)
    return {"items": await cursor.to_list(length=10000 if all else perPage), "total": total}


@router.get("/products/search")
async def product_search(q: str = "", user=Depends(require_admin)):
    if not q.strip():
        return []
    return await db.products.find({"name": {"$regex": re.escape(q.strip()), "$options": "i"}, "isActive": True}, {"_id": 0}).limit(30).to_list(30)


@router.get("/products/export")
async def export_products(user=Depends(require_admin)):
    output = io.StringIO()
    keys = ["sku", "name", "category", "subCategory", "brand", "unit", "salePrice", "purchasePrice", "wholesalePrice", "gstRate", "hsnCode", "currentStock", "minStockLevel", "reorderQty", "location", "barcode", "description", "notes"]
    writer = csv.DictWriter(output, fieldnames=keys, extrasaction="ignore")
    writer.writeheader()
    async for item in db.products.find({}, {"_id": 0}):
        writer.writerow(item)
    return Response(content='\ufeff' + output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=asian-inventory.csv"})


@router.get("/products/template")
async def product_template(user=Depends(require_admin)):
    return Response(content="sku,name,category,brand,unit,salePrice,purchasePrice,gstRate,hsnCode,currentStock,minStockLevel,location\n", media_type="text/csv", headers={"Content-Disposition": "attachment; filename=product-import-template.csv"})


@router.post("/products/import")
async def import_products(file: UploadFile = File(...), user=Depends(require_admin)):
    raw = await file.read(2_000_001)
    if len(raw) > 2_000_000 or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a CSV under 2 MB")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if not reader.fieldnames or "name" not in reader.fieldnames or "salePrice" not in reader.fieldnames:
        raise HTTPException(400, "CSV must include name and salePrice columns")
    created = updated = 0
    for row in reader:
        if not row.get("name", "").strip():
            continue
        try:
            price = float(row["salePrice"])
            purchase = float(row.get("purchasePrice") or 0)
            stock = int(row.get("currentStock") or 0)
            rate = float(row.get("gstRate") or 18)
            if min(price, purchase) < 0 or rate not in (0, 5, 12, 18, 28):
                raise ValueError()
        except ValueError:
            raise HTTPException(400, f"Invalid numeric value for {row['name']}")
        sku = (row.get("sku") or "").strip()
        existing = await db.products.find_one({"sku": sku}, {"_id": 0}) if sku else None
        doc = {"name": row["name"].strip(), "category": row.get("category") or infer_category(row["name"]),
               "brand": row.get("brand") or "", "unit": row.get("unit") or "Piece", "salePrice": price,
               "purchasePrice": purchase, "gstRate": rate, "hsnCode": row.get("hsnCode") or "",
               "currentStock": stock, "minStockLevel": int(row.get("minStockLevel") or 5),
               "location": row.get("location") or "Store 1", "stockCounted": row.get("currentStock") not in (None, ""), "updatedAt": now()}
        if existing:
            await db.products.update_one({"id": existing["id"]}, {"$set": doc})
            updated += 1
        else:
            doc.update({"id": uid(), "sku": sku or f"AH-{uid()[:8].upper()}", "isActive": True, "createdAt": now(), "reorderQty": 10})
            await db.products.insert_one(doc)
            created += 1
    return {"created": created, "updated": updated}


@router.post("/products")
async def create_product(payload: ProductInput, user=Depends(require_admin)):
    doc = payload.model_dump()
    doc["name"] = doc["name"].strip()
    doc.update({"id": uid(), "sku": doc["sku"] or f"AH-{uid()[:8].upper()}", "stockCounted": bool(doc["currentStock"]), "createdAt": now(), "updatedAt": now()})
    if await db.products.find_one({"sku": doc["sku"]}):
        raise HTTPException(409, "SKU already exists")
    await db.products.insert_one(dict(doc))
    return doc


@router.get("/products/images/{image_id}")
async def product_image(image_id: str, user=Depends(require_admin)):
    image = await db.product_images.find_one({"id": image_id}, {"_id": 0})
    if not image:
        raise HTTPException(404, "Image not found")
    return Response(content=image["data"], media_type=image["contentType"])


@router.post("/products/{product_id}/image")
async def upload_product_image(product_id: str, file: UploadFile = File(...), user=Depends(require_admin)):
    if not await db.products.find_one({"id": product_id}):
        raise HTTPException(404, "Product not found")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(400, "Use a JPG, PNG, or WebP image")
    content = await file.read(2_000_001)
    if len(content) > 2_000_000:
        raise HTTPException(400, "Image must be under 2 MB")
    image_id = uid()
    await db.product_images.insert_one({"id": image_id, "data": Binary(content), "contentType": file.content_type})
    url = f"/api/products/images/{image_id}"
    await db.products.update_one({"id": product_id}, {"$set": {"imageUrl": url, "updatedAt": now()}})
    return {"imageUrl": url}


@router.get("/products/{product_id}")
async def get_product(product_id: str, user=Depends(require_admin)):
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(404, "Product not found")
    bills = await db.bills.find({"items.productId": product_id}, {"_id": 0, "id": 1, "number": 1, "date": 1, "grandTotal": 1}).sort("date", -1).limit(30).to_list(30)
    adjustments = await db.stock_adjustments.find({"productId": product_id}, {"_id": 0}).sort("date", -1).limit(30).to_list(30)
    return {**product, "history": {"bills": bills, "adjustments": adjustments}}


@router.put("/products/{product_id}")
async def update_product(product_id: str, payload: dict, user=Depends(require_admin)):
    doc = {key: value for key, value in payload.items() if key in PRODUCT_FIELDS}
    if not doc:
        raise HTTPException(400, "No editable fields provided")
    for key in ("salePrice", "purchasePrice", "wholesalePrice", "gstRate"):
        if key in doc and doc[key] is not None and float(doc[key]) < 0:
            raise HTTPException(400, "Prices and tax rate cannot be negative")
    if "gstRate" in doc and float(doc["gstRate"]) not in (0, 5, 12, 18, 28):
        raise HTTPException(400, "Invalid GST rate")
    if "name" in doc and not str(doc["name"]).strip():
        raise HTTPException(400, "Product name is required")
    if "currentStock" in doc:
        raise HTTPException(400, "Use stock adjustment to change stock")
    doc["updatedAt"] = now()
    product = await db.products.find_one_and_update({"id": product_id}, {"$set": doc}, return_document=ReturnDocument.AFTER, projection={"_id": 0})
    if not product:
        raise HTTPException(404, "Product not found")
    return product


@router.delete("/products/{product_id}")
async def delete_product(product_id: str, user=Depends(require_admin)):
    result = await db.products.update_one({"id": product_id}, {"$set": {"isActive": False, "updatedAt": now()}})
    if not result.matched_count:
        raise HTTPException(404, "Product not found")
    return {"ok": True}


@router.post("/products/{product_id}/adjust")
async def adjust_stock(product_id: str, payload: AdjustmentInput, user=Depends(require_admin)):
    if payload.reason not in {"Purchase", "Return", "Damage", "Theft", "Correction"}:
        raise HTTPException(400, "Choose a valid adjustment reason")
    old = await db.products.find_one_and_update({"id": product_id}, {"$set": {"currentStock": payload.newQty, "stockCounted": True, "updatedAt": now()}}, return_document=ReturnDocument.BEFORE, projection={"_id": 0})
    if not old:
        raise HTTPException(404, "Product not found")
    log = {"id": uid(), "productId": product_id, "previousQty": old["currentStock"], "newQty": payload.newQty,
           "difference": payload.newQty - old["currentStock"], "reason": payload.reason, "notes": payload.notes, "date": now()}
    await db.stock_adjustments.insert_one(dict(log))
    return log


@router.get("/customers")
async def customers(q: str = "", filter: str = "all", user=Depends(require_admin)):
    query = {}
    if q.strip():
        query["$or"] = [{"name": {"$regex": re.escape(q.strip()), "$options": "i"}}, {"phone": {"$regex": re.escape(q.strip()), "$options": "i"}}]
    if filter == "dues":
        query["balance"] = {"$gt": 0}
    return await db.customers.find(query, {"_id": 0}).sort("name", 1).limit(2000).to_list(2000)


@router.post("/customers")
async def create_customer(payload: CustomerInput, user=Depends(require_admin)):
    doc = payload.model_dump()
    doc["phone"] = doc["phone"].strip()
    if doc["phone"] and await db.customers.find_one({"phone": doc["phone"]}):
        raise HTTPException(409, "Phone number already belongs to a customer")
    doc.update({"id": uid(), "balance": 0, "createdAt": now(), "updatedAt": now()})
    stored = dict(doc)
    if not stored["phone"]:
        stored.pop("phone")
    await db.customers.insert_one(stored)
    return doc


@router.get("/customers/{customer_id}")
async def customer_detail(customer_id: str, user=Depends(require_admin)):
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(404, "Customer not found")
    bills = await db.bills.find({"customerId": customer_id, "status": "completed"}, {"_id": 0}).sort("date", -1).to_list(1000)
    payments = await db.payments.find({"customerId": customer_id}, {"_id": 0}).sort("date", -1).to_list(1000)
    quotes = await db.quotations.find({"customerId": customer_id}, {"_id": 0, "id": 1, "number": 1, "date": 1, "grandTotal": 1, "status": 1}).sort("date", -1).to_list(200)
    ledger = sorted([{"type": "Bill", "reference": b["number"], "date": b["date"], "amount": b["grandTotal"], "due": b.get("dueAmount", 0)} for b in bills]
                    + [{"type": "Payment", "reference": p.get("reference") or p["mode"], "date": p["date"], "amount": p["amount"], "due": -p["amount"]} for p in payments], key=lambda row: row["date"])
    running = 0
    for event in ledger:
        running = as_float(running + event["due"])
        event["balance"] = running
    return {**customer, "bills": bills, "payments": payments, "quotations": quotes, "ledger": list(reversed(ledger))}


@router.put("/customers/{customer_id}")
async def update_customer(customer_id: str, payload: dict, user=Depends(require_admin)):
    doc = {k: v for k, v in payload.items() if k in {"name", "phone", "address", "gstin", "email", "creditLimit", "notes"}}
    if not doc:
        raise HTTPException(400, "No fields provided")
    if "name" in doc and not str(doc["name"]).strip():
        raise HTTPException(400, "Name is required")
    if doc.get("phone"):
        duplicate = await db.customers.find_one({"phone": doc["phone"], "id": {"$ne": customer_id}})
        if duplicate:
            raise HTTPException(409, "Phone number already belongs to a customer")
    unset = {"phone": ""} if "phone" in doc and not doc["phone"] else {}
    if unset:
        doc.pop("phone")
    doc["updatedAt"] = now()
    update = {"$set": doc}
    if unset:
        update["$unset"] = unset
    item = await db.customers.find_one_and_update({"id": customer_id}, update, return_document=ReturnDocument.AFTER, projection={"_id": 0})
    if not item:
        raise HTTPException(404, "Customer not found")
    return item


@router.post("/customers/{customer_id}/payment")
async def record_payment(customer_id: str, payload: PaymentInput, user=Depends(require_admin)):
    if payload.mode not in {"Cash", "UPI", "Card", "Cheque"}:
        raise HTTPException(400, "Invalid payment mode")
    customer = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(404, "Customer not found")
    if as_float(payload.amount) > as_float(customer["balance"]):
        raise HTTPException(400, "Payment exceeds outstanding balance")
    doc = {"id": uid(), "customerId": customer_id, "amount": as_float(payload.amount), "mode": payload.mode,
           "reference": payload.reference, "notes": payload.notes, "date": now()}
    await db.payments.insert_one(dict(doc))
    await db.customers.update_one({"id": customer_id}, {"$inc": {"balance": -doc["amount"]}, "$set": {"updatedAt": now()}})
    return doc


@router.get("/settings")
async def get_settings(user=Depends(require_admin)):
    return await db.settings.find_one({"id": "default"}, {"_id": 0})


@router.put("/settings")
async def update_settings(payload: dict, user=Depends(require_admin)):
    doc = {key: value for key, value in payload.items() if key in SETTING_FIELDS}
    if not doc:
        raise HTTPException(400, "No editable settings provided")
    if "printFormat" in doc and doc["printFormat"] not in ("thermal", "a4", "a5"):
        raise HTTPException(400, "Invalid print format")
    return await db.settings.find_one_and_update({"id": "default"}, {"$set": doc}, return_document=ReturnDocument.AFTER, projection={"_id": 0})


@router.post("/inquiries")
async def submit_inquiry(payload: InquiryInput):
    doc = {"id": uid(), **payload.model_dump(), "date": now(), "status": "new"}
    await db.inquiries.insert_one(dict(doc))
    return {"ok": True, "message": "Thanks! The store will be in touch."}


@router.get("/inquiries")
async def list_inquiries(user=Depends(require_admin)):
    return await db.inquiries.find({}, {"_id": 0}).sort("date", -1).limit(100).to_list(100)