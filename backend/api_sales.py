import csv
import io
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from core import IST, as_float, db, fy, money, next_number, now, require_admin, uid
from pdf_export import render_document

router = APIRouter(tags=["sales"])


class LineInput(BaseModel):
    productId: str | None = None
    name: str | None = None
    quantity: int = Field(default=1, ge=1, le=100000)
    unitPrice: float | None = Field(default=None, ge=0)
    discountType: str | None = None
    discountValue: float = Field(default=0, ge=0)
    remarks: str = ""
    gstRate: float | None = None


class SaleInput(BaseModel):
    items: list[LineInput] = Field(min_length=1)
    customerId: str | None = None
    customerName: str = "Walk-in Customer"
    customerPhone: str = ""
    customerAddress: str = ""
    customerGstin: str = ""
    store: str = "Store 1"
    stateCode: str = "27"
    paymentMode: str = "Cash"
    amountReceived: float | None = Field(default=None, ge=0)
    upiTransactionId: str = ""
    overallDiscountType: str | None = None
    overallDiscountValue: float = Field(default=0, ge=0)
    notes: str = ""
    idempotencyKey: str | None = None
    sourceQuotationId: str | None = None


class QuoteInput(BaseModel):
    items: list[LineInput] = Field(min_length=1)
    customerId: str | None = None
    customerName: str = Field(min_length=1)
    customerPhone: str = ""
    customerAddress: str = ""
    customerGstin: str = ""
    stateCode: str = "27"
    validityDays: int = Field(default=7, ge=1, le=365)
    terms: str = "Prices subject to stock availability. Transportation charges extra."
    notes: str = ""
    status: str = "draft"
    overallDiscountType: str | None = None
    overallDiscountValue: float = Field(default=0, ge=0)


async def calculated_lines(items, state_code="27", overall_type=None, overall_value=0):
    product_ids = list({line.productId for line in items if line.productId})
    products = {p["id"]: p for p in await db.products.find({"id": {"$in": product_ids}}, {"_id": 0}).to_list(1000)}
    built = []
    subtotal = Decimal("0")
    item_discount_total = Decimal("0")
    for line in items:
        product = products.get(line.productId) if line.productId else None
        if line.productId and (not product or not product.get("isActive", True)):
            raise HTTPException(400, f"A selected product is unavailable: {line.productId}")
        name = product["name"] if product else (line.name or "").strip()
        if not name:
            raise HTTPException(400, "Every line needs a product name")
        price = money(line.unitPrice if line.unitPrice is not None else product["salePrice"] if product else 0)
        gross = money(price * line.quantity)
        if line.discountType not in (None, "amount", "percentage"):
            raise HTTPException(400, "Invalid discount type")
        discount = money(gross * money(line.discountValue) / 100) if line.discountType == "percentage" else money(line.discountValue) if line.discountType == "amount" else Decimal("0")
        if discount > gross:
            raise HTTPException(400, f"Discount exceeds price of {name}")
        subtotal += gross
        item_discount_total += discount
        built.append({"id": uid(), "productId": line.productId, "productName": name, "quantity": line.quantity,
                      "unit": product.get("unit", "Piece") if product else "Piece", "unitPrice": float(price),
                      "grossAmount": float(gross), "discountType": line.discountType,
                      "discountValue": line.discountValue, "itemDiscount": float(discount),
                      "gstRate": product["gstRate"] if product else (line.gstRate if line.gstRate in (0, 5, 12, 18, 28) else 18),
                      "hsnCode": product.get("hsnCode", "") if product else "", "remarks": line.remarks,
                      "purchasePrice": product.get("purchasePrice", 0) if product else 0})
    before_bill_discount = subtotal - item_discount_total
    if overall_type not in (None, "amount", "percentage"):
        raise HTTPException(400, "Invalid overall discount type")
    overall_discount = money(before_bill_discount * money(overall_value) / 100) if overall_type == "percentage" else money(overall_value) if overall_type == "amount" else Decimal("0")
    if overall_discount > before_bill_discount:
        raise HTTPException(400, "Overall discount exceeds bill value")
    remaining = overall_discount
    taxable_total = cgst_total = sgst_total = igst_total = Decimal("0")
    for index, item in enumerate(built):
        line_after_discount = money(item["grossAmount"] - item["itemDiscount"])
        allocation = min(remaining, money(overall_discount * line_after_discount / before_bill_discount)) if before_bill_discount and index < len(built) - 1 else remaining
        remaining -= allocation
        taxable = money(line_after_discount - allocation)
        rate = money(item["gstRate"])
        cgst = money(taxable * rate / 200) if state_code == "27" else Decimal("0")
        sgst = money(taxable * rate / 200) if state_code == "27" else Decimal("0")
        igst = money(taxable * rate / 100) if state_code != "27" else Decimal("0")
        item.update({"discountAmount": float(money(money(item["itemDiscount"]) + allocation)), "taxableAmount": float(taxable),
                     "cgst": float(cgst), "sgst": float(sgst), "igst": float(igst),
                     "totalAmount": float(money(taxable + cgst + sgst + igst))})
        taxable_total += taxable
        cgst_total += cgst
        sgst_total += sgst
        igst_total += igst
    total_tax = cgst_total + sgst_total + igst_total
    unrounded = taxable_total + total_tax
    grand = unrounded.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return built, {"subtotal": float(money(subtotal)), "discountAmount": float(money(item_discount_total + overall_discount)),
                   "overallDiscountAmount": float(overall_discount), "taxableAmount": float(taxable_total),
                   "cgst": float(cgst_total), "sgst": float(sgst_total), "igst": float(igst_total),
                   "totalTax": float(total_tax), "roundOff": float(money(grand - unrounded)), "grandTotal": float(grand)}


async def persist_bill(payload: SaleInput):
    if payload.store not in ("Store 1", "Store 2") or payload.paymentMode not in ("Cash", "UPI", "Card", "Credit", "Mixed"):
        raise HTTPException(400, "Invalid store or payment mode")
    if payload.idempotencyKey:
        existing = await db.bills.find_one({"idempotencyKey": payload.idempotencyKey}, {"_id": 0})
        if existing:
            return existing
    customer = await db.customers.find_one({"id": payload.customerId}, {"_id": 0}) if payload.customerId else None
    if payload.customerId and not customer:
        raise HTTPException(400, "Customer not found")
    gstin = (payload.customerGstin or (customer or {}).get("gstin", "")).upper().strip()
    state_code = gstin[:2] if len(gstin) >= 2 and gstin[:2].isdigit() else payload.stateCode
    if not state_code.isdigit() or len(state_code) != 2:
        raise HTTPException(400, "State code must have two digits")
    items, totals = await calculated_lines(payload.items, state_code, payload.overallDiscountType, payload.overallDiscountValue)
    total = totals["grandTotal"]
    received = money(payload.amountReceived if payload.amountReceived is not None else 0 if payload.paymentMode in ("Credit", "Mixed") else total)
    if payload.paymentMode in ("Credit", "Mixed") and not customer:
        raise HTTPException(400, "Select a saved customer for a credit or partial-payment bill")
    if payload.paymentMode == "Credit" and received > 0:
        raise HTTPException(400, "Use Mixed payment for partial credit")
    if payload.paymentMode in ("UPI", "Card") and received < money(total):
        received = money(total)
    if payload.paymentMode == "Cash" and received < money(total):
        raise HTTPException(400, "Amount received is less than the bill total")
    due = money(max(Decimal("0"), money(total) - received)) if payload.paymentMode in ("Credit", "Mixed") else Decimal("0")
    if customer and customer.get("creditLimit", 0) > 0 and money(customer.get("balance", 0)) + due > money(customer["creditLimit"]):
        raise HTTPException(400, "Customer credit limit would be exceeded")
    doc = {"id": uid(), "number": await next_number("bill"), "date": now(), "financialYear": fy(),
           "customerId": payload.customerId, "customerName": (customer or {}).get("name") or payload.customerName or "Walk-in Customer",
           "customerPhone": (customer or {}).get("phone") or payload.customerPhone,
           "customerAddress": (customer or {}).get("address") or payload.customerAddress, "customerGstin": gstin,
           "stateCode": state_code, "placeOfSupply": "Maharashtra (27)" if state_code == "27" else f"State code {state_code}",
           "store": payload.store, "paymentMode": payload.paymentMode, "amountReceived": float(received),
           "changeReturned": float(max(Decimal("0"), received - money(total))) if payload.paymentMode == "Cash" else 0,
           "dueAmount": float(due), "upiTransactionId": payload.upiTransactionId,
           "overallDiscountType": payload.overallDiscountType, "overallDiscountValue": payload.overallDiscountValue,
           "notes": payload.notes, "status": "completed", "items": items, "sourceQuotationId": payload.sourceQuotationId,
           "idempotencyKey": payload.idempotencyKey, **totals}
    await db.bills.insert_one(dict(doc))
    for item in items:
        if item["productId"]:
            await db.products.update_one({"id": item["productId"]}, {"$inc": {"currentStock": -item["quantity"]}, "$set": {"updatedAt": now()}})
    if customer and due:
        await db.customers.update_one({"id": customer["id"]}, {"$inc": {"balance": float(due)}, "$set": {"updatedAt": now()}})
    return doc


@router.get("/billing/next-number")
async def bill_next_number(user=Depends(require_admin)):
    setting = await db.settings.find_one({"id": "default"}, {"_id": 0})
    return {"number": f"AH/{fy()}/{setting['nextBillNumber']:05d}"}


@router.get("/billing/held")
async def held_bills(user=Depends(require_admin)):
    return await db.held_bills.find({}, {"_id": 0}).sort("date", -1).to_list(100)


@router.post("/billing/held")
async def hold_bill(payload: dict, user=Depends(require_admin)):
    doc = {"id": uid(), "date": now(), "draft": payload, "customerName": payload.get("customerName") or "Walk-in Customer",
           "itemCount": len(payload.get("items") or [])}
    if not doc["itemCount"]:
        raise HTTPException(400, "Add items before holding a bill")
    await db.held_bills.insert_one(dict(doc))
    return doc


@router.delete("/billing/held/{held_id}")
async def remove_held(held_id: str, user=Depends(require_admin)):
    result = await db.held_bills.delete_one({"id": held_id})
    if not result.deleted_count:
        raise HTTPException(404, "Held bill not found")
    return {"ok": True}


@router.get("/billing")
async def list_bills(q: str = "", limit: int = Query(100, ge=1, le=2000), user=Depends(require_admin)):
    query = {"$or": [{"number": {"$regex": q, "$options": "i"}}, {"customerName": {"$regex": q, "$options": "i"}}]} if q else {}
    return await db.bills.find(query, {"_id": 0}).sort("date", -1).limit(limit).to_list(limit)


@router.post("/billing")
async def create_bill(payload: SaleInput, user=Depends(require_admin)):
    return await persist_bill(payload)


@router.get("/billing/{bill_id}")
async def get_bill(bill_id: str, user=Depends(require_admin)):
    doc = await db.bills.find_one({"id": bill_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Bill not found")
    return doc


@router.put("/billing/{bill_id}")
async def update_bill_status(bill_id: str, payload: dict, user=Depends(require_admin)):
    if payload.get("status") not in ("completed", "cancelled"):
        raise HTTPException(400, "Invalid bill status")
    current = await db.bills.find_one({"id": bill_id}, {"_id": 0})
    if not current:
        raise HTTPException(404, "Bill not found")
    if current["status"] == "cancelled" and payload["status"] == "completed":
        raise HTTPException(400, "A cancelled bill cannot be reopened")
    if current["status"] == "completed" and payload["status"] == "cancelled":
        for item in current["items"]:
            if item.get("productId"):
                await db.products.update_one({"id": item["productId"]}, {"$inc": {"currentStock": item["quantity"]}})
        if current.get("customerId") and current.get("dueAmount"):
            await db.customers.update_one({"id": current["customerId"]}, {"$inc": {"balance": -current["dueAmount"]}})
    return await db.bills.find_one_and_update({"id": bill_id}, {"$set": {"status": payload["status"]}}, return_document=ReturnDocument.AFTER, projection={"_id": 0})


@router.get("/billing/{bill_id}/pdf")
async def bill_pdf(bill_id: str, format: str = "thermal", user=Depends(require_admin)):
    doc = await db.bills.find_one({"id": bill_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Bill not found")
    if format not in ("thermal", "a4", "a5"):
        raise HTTPException(400, "Invalid print format")
    setting = await db.settings.find_one({"id": "default"}, {"_id": 0})
    content = render_document(doc, setting, "bill", format)
    return Response(content=content, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{doc["number"].replace("/", "-")}.pdf"'})


def mark_expired(doc):
    if doc["status"] in ("draft", "sent") and doc["validUntil"] < now():
        doc["status"] = "expired"
    return doc


@router.get("/quotations")
async def list_quotes(q: str = "", status: str = "", user=Depends(require_admin)):
    query = {"$or": [{"number": {"$regex": q, "$options": "i"}}, {"customerName": {"$regex": q, "$options": "i"}}]} if q else {}
    docs = await db.quotations.find(query, {"_id": 0}).sort("date", -1).limit(2000).to_list(2000)
    return [doc for doc in map(mark_expired, docs) if not status or doc["status"] == status]


@router.post("/quotations")
async def create_quote(payload: QuoteInput, user=Depends(require_admin)):
    if payload.customerId and not await db.customers.find_one({"id": payload.customerId}):
        raise HTTPException(400, "Customer not found")
    items, totals = await calculated_lines(payload.items, payload.stateCode, payload.overallDiscountType, payload.overallDiscountValue)
    if payload.status not in ("draft", "sent", "accepted", "rejected"):
        raise HTTPException(400, "Invalid quotation status")
    document = {"id": uid(), "number": await next_number("quote"), "date": now(),
                "validUntil": (datetime.now(timezone.utc) + timedelta(days=payload.validityDays)).isoformat(),
                "validityDays": payload.validityDays, "customerId": payload.customerId,
                "customerName": payload.customerName.strip(), "customerPhone": payload.customerPhone,
                "customerAddress": payload.customerAddress, "customerGstin": payload.customerGstin,
                "stateCode": payload.stateCode, "terms": payload.terms, "notes": payload.notes,
                "status": payload.status, "convertedBillId": None, "items": items,
                "overallDiscountType": payload.overallDiscountType, "overallDiscountValue": payload.overallDiscountValue, **totals}
    await db.quotations.insert_one(dict(document))
    return document


@router.get("/quotations/{quote_id}")
async def get_quote(quote_id: str, user=Depends(require_admin)):
    doc = await db.quotations.find_one({"id": quote_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Quotation not found")
    return mark_expired(doc)


@router.put("/quotations/{quote_id}")
async def update_quote(quote_id: str, payload: dict, user=Depends(require_admin)):
    doc = await db.quotations.find_one({"id": quote_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Quotation not found")
    if doc["status"] == "converted":
        raise HTTPException(400, "Converted quotations cannot be edited")
    allowed = {k: v for k, v in payload.items() if k in {"customerName", "customerPhone", "customerAddress", "customerGstin", "customerId", "terms", "notes", "status", "validityDays", "items", "overallDiscountType", "overallDiscountValue", "stateCode"}}
    if allowed.get("status") not in (None, "draft", "sent", "accepted", "rejected", "expired"):
        raise HTTPException(400, "Invalid quotation status")
    if "validityDays" in allowed:
        allowed["validUntil"] = (datetime.fromisoformat(doc["date"]) + timedelta(days=int(allowed["validityDays"]))).isoformat()
    if "items" in allowed or "overallDiscountValue" in allowed:
        lines = [LineInput(**{**line, "name": line.get("name") or line.get("productName")}) for line in allowed.get("items", doc["items"])]
        items, totals = await calculated_lines(lines, allowed.get("stateCode", doc.get("stateCode", "27")), allowed.get("overallDiscountType", doc.get("overallDiscountType")), allowed.get("overallDiscountValue", doc.get("overallDiscountValue", 0)))
        allowed.update({"items": items, **totals})
    allowed["updatedAt"] = now()
    return await db.quotations.find_one_and_update({"id": quote_id}, {"$set": allowed}, return_document=ReturnDocument.AFTER, projection={"_id": 0})


@router.post("/quotations/{quote_id}/convert")
async def convert_quote(quote_id: str, payload: dict, user=Depends(require_admin)):
    quote = await db.quotations.find_one({"id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(404, "Quotation not found")
    if quote["status"] == "converted":
        raise HTTPException(400, "Quotation is already converted")
    if quote["status"] != "accepted" or quote["validUntil"] < now():
        raise HTTPException(400, "Accept an active quotation before converting it to a bill")
    lines = [LineInput(productId=item.get("productId"), name=item["productName"], quantity=item["quantity"],
                       unitPrice=item["unitPrice"], discountType="amount", discountValue=item.get("itemDiscount", 0),
                       gstRate=item["gstRate"], remarks=item.get("remarks", "")) for item in quote["items"]]
    bill = await persist_bill(SaleInput(items=lines, customerId=quote.get("customerId"), customerName=quote["customerName"],
                                       customerPhone=quote.get("customerPhone", ""), customerAddress=quote.get("customerAddress", ""),
                                       customerGstin=quote.get("customerGstin", ""), stateCode=quote.get("stateCode", "27"),
                                       overallDiscountType=quote.get("overallDiscountType"), overallDiscountValue=quote.get("overallDiscountValue", 0),
                                       paymentMode=payload.get("paymentMode", "Cash"), amountReceived=payload.get("amountReceived"),
                                       sourceQuotationId=quote_id, idempotencyKey=f"quote-{quote_id}"))
    await db.quotations.update_one({"id": quote_id}, {"$set": {"status": "converted", "convertedBillId": bill["id"], "updatedAt": now()}})
    return bill


@router.get("/quotations/{quote_id}/pdf")
async def quote_pdf(quote_id: str, user=Depends(require_admin)):
    doc = await db.quotations.find_one({"id": quote_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Quotation not found")
    setting = await db.settings.find_one({"id": "default"}, {"_id": 0})
    content = render_document(doc, setting, "quotation", "a4")
    return Response(content=content, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{doc["number"].replace("/", "-")}.pdf"'})


@router.get("/reports/overview")
async def overview(user=Depends(require_admin)):
    today = datetime.now(IST).date().isoformat()
    yesterday = (datetime.now(IST).date() - timedelta(days=1)).isoformat()
    bills = await db.bills.find({"status": "completed"}, {"_id": 0}).sort("date", -1).limit(10000).to_list(10000)
    def local_day(date):
        return datetime.fromisoformat(date).astimezone(IST).date().isoformat()
    today_bills = [bill for bill in bills if local_day(bill["date"]) == today]
    yesterday_bills = [bill for bill in bills if local_day(bill["date"]) == yesterday]
    quotes = await db.quotations.find({}, {"_id": 0}).to_list(5000)
    low = await db.products.count_documents({"isActive": True, "$expr": {"$lte": ["$currentStock", "$minStockLevel"]}})
    trend = []
    for i in range(6, -1, -1):
        day = (datetime.now(IST).date() - timedelta(days=i)).isoformat()
        trend.append({"date": day, "sales": round(sum(b["grandTotal"] for b in bills if local_day(b["date"]) == day), 2)})
    top = defaultdict(lambda: {"quantity": 0, "revenue": 0})
    for bill in bills:
        for item in bill["items"]:
            top[item["productName"]]["quantity"] += item["quantity"]
            top[item["productName"]]["revenue"] += item["totalAmount"]
    return {"todaySales": round(sum(b["grandTotal"] for b in today_bills), 2), "yesterdaySales": round(sum(b["grandTotal"] for b in yesterday_bills), 2),
            "todayBills": len(today_bills), "pendingQuotes": sum(1 for q in quotes if mark_expired(q)["status"] in ("draft", "sent", "accepted")),
            "lowStock": low, "totalProducts": await db.products.count_documents({"isActive": True}), "trend": trend,
            "topProducts": [{"name": name, **stats} for name, stats in sorted(top.items(), key=lambda entry: entry[1]["quantity"], reverse=True)[:10]],
            "recentBills": bills[:8], "recentQuotes": sorted(quotes, key=lambda q: q["date"], reverse=True)[:5]}


async def report_bills(start=None, end=None):
    docs = await db.bills.find({"status": "completed"}, {"_id": 0}).to_list(50000)
    def local_day(doc):
        return datetime.fromisoformat(doc["date"]).astimezone(IST).date().isoformat()
    return [doc for doc in docs if (not start or local_day(doc) >= start) and (not end or local_day(doc) <= end)]


@router.get("/reports/daily")
async def daily_report(date: str = "", user=Depends(require_admin)):
    day = date or datetime.now(IST).date().isoformat()
    bills = await report_bills(day, day)
    return {"date": day, "bills": bills, "revenue": round(sum(b["grandTotal"] for b in bills), 2), "tax": round(sum(b["totalTax"] for b in bills), 2), "count": len(bills)}


@router.get("/reports/monthly")
async def monthly_report(month: str = "", user=Depends(require_admin)):
    current = month or datetime.now(IST).strftime("%Y-%m")
    bills = await report_bills(current + "-01", current + "-31")
    revenue = sum(b["grandTotal"] for b in bills)
    costs = {p["id"]: p.get("purchasePrice", 0) for p in await db.products.find({}, {"_id": 0, "id": 1, "purchasePrice": 1}).to_list(10000)}
    cogs = sum(sum(line.get("purchasePrice", costs.get(line.get("productId"), 0)) * line["quantity"] for line in b["items"]) for b in bills)
    return {"month": current, "revenue": round(revenue, 2), "cogs": round(cogs, 2), "grossProfit": round(sum(b["taxableAmount"] for b in bills) - cogs, 2),
            "tax": round(sum(b["totalTax"] for b in bills), 2), "billCount": len(bills), "averageBill": round(revenue / len(bills), 2) if bills else 0}


@router.get("/reports/products")
async def product_report(fromDate: str = "", toDate: str = "", user=Depends(require_admin)):
    bills = await report_bills(fromDate, toDate)
    stats = defaultdict(lambda: {"quantity": 0, "revenue": 0})
    for bill in bills:
        for item in bill["items"]:
            stats[item["productName"]]["quantity"] += item["quantity"]
            stats[item["productName"]]["revenue"] += item["totalAmount"]
    return [{"name": name, "quantity": val["quantity"], "revenue": round(val["revenue"], 2)} for name, val in sorted(stats.items(), key=lambda x: x[1]["revenue"], reverse=True)]


@router.get("/reports/categories")
async def category_report(fromDate: str = "", toDate: str = "", user=Depends(require_admin)):
    bills = await report_bills(fromDate, toDate)
    products = {p["id"]: p.get("category", "General & Misc") for p in await db.products.find({}, {"_id": 0, "id": 1, "category": 1}).to_list(10000)}
    stats = defaultdict(lambda: {"quantity": 0, "revenue": 0})
    for bill in bills:
        for line in bill["items"]:
            category = products.get(line.get("productId"), "Custom items")
            stats[category]["quantity"] += line["quantity"]
            stats[category]["revenue"] += line["totalAmount"]
    return [{"category": name, "quantity": values["quantity"], "revenue": round(values["revenue"], 2)} for name, values in sorted(stats.items(), key=lambda x: x[1]["revenue"], reverse=True)]


@router.get("/reports/sales")
async def sales_report(fromDate: str = "", toDate: str = "", user=Depends(require_admin)):
    bills = await report_bills(fromDate, toDate)
    costs = {p["id"]: p.get("purchasePrice", 0) for p in await db.products.find({}, {"_id": 0, "id": 1, "purchasePrice": 1}).to_list(10000)}
    cogs = sum(sum(line.get("purchasePrice", costs.get(line.get("productId"), 0)) * line["quantity"] for line in bill["items"]) for bill in bills)
    return {"fromDate": fromDate, "toDate": toDate, "bills": bills, "count": len(bills),
            "revenue": round(sum(b["grandTotal"] for b in bills), 2), "tax": round(sum(b["totalTax"] for b in bills), 2),
            "cogs": round(cogs, 2), "grossProfit": round(sum(b["taxableAmount"] for b in bills) - cogs, 2)}


@router.get("/reports/gst")
async def gst_report(fromDate: str = "", toDate: str = "", user=Depends(require_admin)):
    bills = await report_bills(fromDate, toDate)
    return {"count": len(bills), "taxable": round(sum(b["taxableAmount"] for b in bills), 2),
            "cgst": round(sum(b["cgst"] for b in bills), 2), "sgst": round(sum(b["sgst"] for b in bills), 2),
            "igst": round(sum(b["igst"] for b in bills), 2), "totalTax": round(sum(b["totalTax"] for b in bills), 2)}


@router.get("/reports/stock")
async def stock_report(user=Depends(require_admin)):
    products = await db.products.find({"isActive": True}, {"_id": 0}).to_list(10000)
    low = [p for p in products if p["currentStock"] <= p["minStockLevel"]]
    return {"totalProducts": len(products), "lowStock": len(low), "unCounted": sum(not p.get("stockCounted") for p in products),
            "stockValue": round(sum(p["currentStock"] * p.get("purchasePrice", 0) for p in products), 2),
            "items": sorted(low, key=lambda p: p["currentStock"])[:100]}


@router.get("/reports/customers")
async def customer_report(user=Depends(require_admin)):
    customers = await db.customers.find({}, {"_id": 0}).to_list(10000)
    return {"outstanding": round(sum(c.get("balance", 0) for c in customers), 2), "count": len(customers),
            "withDues": sum(c.get("balance", 0) > 0 for c in customers), "topDue": sorted(customers, key=lambda c: c.get("balance", 0), reverse=True)[:10]}


@router.get("/reports/quotations")
async def quote_report(user=Depends(require_admin)):
    quotes = await db.quotations.find({}, {"_id": 0, "status": 1}).to_list(10000)
    converted = sum(q["status"] == "converted" for q in quotes)
    return {"count": len(quotes), "converted": converted, "conversionRate": round(converted * 100 / len(quotes), 1) if quotes else 0}