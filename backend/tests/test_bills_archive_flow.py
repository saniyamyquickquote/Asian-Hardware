"""Bills archive + print events + cancel + convert-event regression (iteration 3)."""
import os
import uuid
from datetime import datetime

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")


@pytest.fixture(scope="module")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="module")
def admin(base_url):
    s = requests.Session()
    r = s.post(f"{base_url}/api/auth/login", json={"username": "admin", "password": "asian2019"}, timeout=30)
    assert r.status_code == 200
    return s


@pytest.fixture(scope="module")
def grinding(admin, base_url):
    r = admin.get(f"{base_url}/api/products/search", params={"q": "GRINDING"}, timeout=30)
    assert r.status_code == 200
    return next(p for p in r.json() if p["name"] == "GRINDING WHEEL")


def _line(item, qty=1):
    return {"productId": item["id"], "name": item["name"], "quantity": qty,
            "unitPrice": item["salePrice"], "discountType": "amount", "discountValue": 0,
            "gstRate": item.get("gstRate", 18)}


def _make_bill(admin, base_url, grinding, **extra):
    body = {"items": [_line(grinding, 1)], "paymentMode": "Cash", "amountReceived": 5000,
            "store": "Store 1", "stateCode": "27",
            "idempotencyKey": f"arch-{uuid.uuid4().hex}"}
    body.update(extra)
    r = admin.post(f"{base_url}/api/billing", json=body, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


# --- POST /billing new fields ---
def test_create_bill_has_new_metadata(admin, base_url, grinding):
    b = _make_bill(admin, base_url, grinding)
    assert b["createdBy"] == "admin"
    assert b["printCount"] == 0
    assert b["shareCount"] == 0
    assert isinstance(b["events"], list) and len(b["events"]) >= 1
    ev = b["events"][0]
    assert ev["type"] == "created"
    assert ev["by"] == "admin"
    assert "at" in ev


# --- PDF action=print / download event + counter ---
def test_pdf_print_and_download_events(admin, base_url, grinding):
    b = _make_bill(admin, base_url, grinding)
    bid = b["id"]

    r = admin.get(f"{base_url}/api/billing/{bid}/pdf", params={"format": "thermal", "action": "print"}, timeout=60)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    d1 = admin.get(f"{base_url}/api/billing/{bid}", timeout=30).json()
    assert d1["printCount"] == 1
    assert "lastPrintedAt" in d1
    assert any(e["type"] == "printed" for e in d1["events"])

    r2 = admin.get(f"{base_url}/api/billing/{bid}/pdf", params={"format": "a4", "action": "download"}, timeout=60)
    assert r2.status_code == 200
    d2 = admin.get(f"{base_url}/api/billing/{bid}", timeout=30).json()
    assert d2["printCount"] == 1  # unchanged
    assert any(e["type"] == "downloaded" for e in d2["events"])

    # No action → no new event
    before = len(d2["events"])
    r3 = admin.get(f"{base_url}/api/billing/{bid}/pdf", params={"format": "a4"}, timeout=60)
    assert r3.status_code == 200
    d3 = admin.get(f"{base_url}/api/billing/{bid}", timeout=30).json()
    assert len(d3["events"]) == before


# --- POST /billing/{id}/events ---
def test_events_shared_note_validation(admin, base_url, grinding):
    b = _make_bill(admin, base_url, grinding)
    bid = b["id"]

    r = admin.post(f"{base_url}/api/billing/{bid}/events", json={"type": "shared", "channel": "whatsapp"}, timeout=30)
    assert r.status_code == 200
    assert r.json()["shareCount"] == 1
    assert any(e["type"] == "shared" for e in r.json()["events"])

    r2 = admin.post(f"{base_url}/api/billing/{bid}/events", json={"type": "note", "detail": "Delivered Monday"}, timeout=30)
    assert r2.status_code == 200
    assert any(e["type"] == "note" and e["detail"] == "Delivered Monday" for e in r2.json()["events"])

    assert admin.post(f"{base_url}/api/billing/{bid}/events", json={"type": "note", "detail": ""}, timeout=30).status_code == 400
    assert admin.post(f"{base_url}/api/billing/{bid}/events", json={"type": "bogus"}, timeout=30).status_code == 400


# --- List /billing paginated + summary + filters ---
def test_list_bills_paginated_object(admin, base_url, grinding):
    _make_bill(admin, base_url, grinding)
    r = admin.get(f"{base_url}/api/billing", params={"perPage": 5, "page": 1}, timeout=30)
    assert r.status_code == 200
    body = r.json()
    for key in ("items", "total", "page", "perPage", "pages", "summary"):
        assert key in body
    assert body["page"] == 1
    assert body["perPage"] == 5
    assert body["pages"] >= 1
    for key in ("count", "completed", "cancelled", "sales", "tax", "due", "items"):
        assert key in body["summary"]
    # events excluded from list
    if body["items"]:
        assert "events" not in body["items"][0]


def test_list_bills_filters(admin, base_url, grinding):
    b = _make_bill(admin, base_url, grinding, customerName=f"TEST_LIST_{uuid.uuid4().hex[:6]}")
    # q by number
    r = admin.get(f"{base_url}/api/billing", params={"q": b["number"]}, timeout=30)
    assert r.status_code == 200
    assert any(x["number"] == b["number"] for x in r.json()["items"])
    # q by customerName
    r2 = admin.get(f"{base_url}/api/billing", params={"q": b["customerName"][:12]}, timeout=30)
    assert r2.status_code == 200
    assert r2.json()["total"] >= 1
    # q by item name
    r3 = admin.get(f"{base_url}/api/billing", params={"q": "GRIND"}, timeout=30)
    assert r3.status_code == 200 and r3.json()["total"] >= 1
    # today range
    today = datetime.utcnow().date().isoformat()
    rt = admin.get(f"{base_url}/api/billing", params={"start": today, "end": today}, timeout=30)
    assert rt.status_code == 200 and rt.json()["total"] >= 1
    # past range
    rp = admin.get(f"{base_url}/api/billing", params={"start": "2020-01-01", "end": "2020-01-02"}, timeout=30)
    assert rp.status_code == 200 and rp.json()["total"] == 0
    # paymentMode
    rc = admin.get(f"{base_url}/api/billing", params={"paymentMode": "Cash"}, timeout=30)
    assert rc.status_code == 200
    assert all(x["paymentMode"] == "Cash" for x in rc.json()["items"])
    # gst true/false
    rg = admin.get(f"{base_url}/api/billing", params={"gst": "false"}, timeout=30)
    assert rg.status_code == 200
    assert all(x["includeGst"] is False for x in rg.json()["items"])
    # store
    rs = admin.get(f"{base_url}/api/billing", params={"store": "Store 1"}, timeout=30)
    assert rs.status_code == 200
    # invalid date
    rd = admin.get(f"{base_url}/api/billing", params={"start": "abc"}, timeout=30)
    assert rd.status_code == 400


def test_list_bills_pagination_math(admin, base_url):
    r = admin.get(f"{base_url}/api/billing", params={"perPage": 3, "page": 1}, timeout=30)
    body = r.json()
    import math
    assert body["pages"] == max(1, math.ceil(body["total"] / 3))


# --- CSV export ---
def test_export_csv(admin, base_url):
    r = admin.get(f"{base_url}/api/billing/export", timeout=60)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    first_line = r.text.split("\n", 1)[0]
    assert first_line.startswith("Bill No,Date (IST),Type,Status")
    assert "Item Details" in first_line


# --- Cancel with reason: restores stock + khata ---
def test_cancel_bill_requires_reason_and_restores(admin, base_url, grinding):
    # Create customer for credit bill
    cust = admin.post(f"{base_url}/api/customers",
                      json={"name": f"TEST_CANCEL_{uuid.uuid4().hex[:6]}", "phone": "", "address": "", "gstin": ""},
                      timeout=30).json()
    prod_before = admin.get(f"{base_url}/api/products/{grinding['id']}", timeout=30).json()["currentStock"]

    bill = admin.post(f"{base_url}/api/billing", json={
        "items": [_line(grinding, 2)], "customerId": cust["id"], "paymentMode": "Credit",
        "amountReceived": 0, "store": "Store 1", "stateCode": "27",
        "idempotencyKey": f"cancel-{uuid.uuid4().hex}",
    }, timeout=30).json()
    bid = bill["id"]
    due = bill["dueAmount"]
    cust_bal_before = admin.get(f"{base_url}/api/customers/{cust['id']}", timeout=30).json()["balance"]
    assert cust_bal_before >= due - 0.01

    prod_after_sale = admin.get(f"{base_url}/api/products/{grinding['id']}", timeout=30).json()["currentStock"]
    assert prod_after_sale == prod_before - 2

    # No reason → 400
    r_nr = admin.put(f"{base_url}/api/billing/{bid}", json={"status": "cancelled"}, timeout=30)
    assert r_nr.status_code == 400
    # Reason too short
    r_sr = admin.put(f"{base_url}/api/billing/{bid}", json={"status": "cancelled", "reason": "ab"}, timeout=30)
    assert r_sr.status_code == 400
    # Good reason
    r_ok = admin.put(f"{base_url}/api/billing/{bid}", json={"status": "cancelled", "reason": "Customer returned"}, timeout=30)
    assert r_ok.status_code == 200
    doc = r_ok.json()
    assert doc["status"] == "cancelled"
    assert doc["cancelReason"] == "Customer returned"
    assert doc["cancelledBy"] == "admin"
    assert any(e["type"] == "cancelled" for e in doc["events"])

    prod_after_cancel = admin.get(f"{base_url}/api/products/{grinding['id']}", timeout=30).json()["currentStock"]
    assert prod_after_cancel == prod_before  # restored

    cust_bal_after = admin.get(f"{base_url}/api/customers/{cust['id']}", timeout=30).json()["balance"]
    assert abs(cust_bal_after - (cust_bal_before - due)) < 0.5

    # Cancelling again → same doc, no double restore
    r_again = admin.put(f"{base_url}/api/billing/{bid}", json={"status": "cancelled", "reason": "Customer returned"}, timeout=30)
    assert r_again.status_code == 200
    prod_after_2 = admin.get(f"{base_url}/api/products/{grinding['id']}", timeout=30).json()["currentStock"]
    assert prod_after_2 == prod_before

    # Reopen → 400
    r_reopen = admin.put(f"{base_url}/api/billing/{bid}", json={"status": "completed"}, timeout=30)
    assert r_reopen.status_code == 400


# --- Quote → bill converted event + sourceQuotationNumber ---
def test_convert_quote_adds_event_and_source_number(admin, base_url, grinding):
    q = admin.post(f"{base_url}/api/quotations", json={
        "items": [_line(grinding, 1)], "customerName": f"TEST_CONV_{uuid.uuid4().hex[:6]}",
        "customerPhone": "9999999999", "status": "draft", "validityDays": 7, "stateCode": "27",
    }, timeout=30).json()
    admin.put(f"{base_url}/api/quotations/{q['id']}", json={"status": "accepted"}, timeout=30)
    bill = admin.post(f"{base_url}/api/quotations/{q['id']}/convert", json={"paymentMode": "Cash"}, timeout=30).json()
    assert bill.get("sourceQuotationNumber") == q["number"]
    assert any(e["type"] == "converted" for e in bill.get("events", []))
    detail = admin.get(f"{base_url}/api/billing/{bill['id']}", timeout=30).json()
    assert detail["sourceQuotationNumber"] == q["number"]
    quote_after = admin.get(f"{base_url}/api/quotations/{q['id']}", timeout=30).json()
    assert quote_after.get("convertedBillNumber") == bill["number"]
