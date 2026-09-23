"""GST toggle + PDF + quotation/hold flow regression (iteration 2)."""
import os
import re
import uuid

import pytest
import requests
from dotenv import load_dotenv

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None

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
    target = next((p for p in r.json() if p["name"] == "GRINDING WHEEL"), None)
    assert target is not None
    return target


def _line(item, qty=1):
    return {
        "productId": item["id"],
        "name": item["name"],
        "quantity": qty,
        "unitPrice": item["salePrice"],
        "discountType": "amount",
        "discountValue": 0,
        "gstRate": item.get("gstRate", 18),
    }


# --- Billing: includeGst=false (default / omitted) ---
def test_billing_default_no_gst(admin, base_url, grinding):
    payload = {
        "items": [_line(grinding, 3)],
        "paymentMode": "Cash",
        "amountReceived": 5000,
        "store": "Store 1",
        "stateCode": "27",
        "idempotencyKey": f"nogst-{uuid.uuid4().hex}",
    }
    r = admin.post(f"{base_url}/api/billing", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["includeGst"] is False
    assert b["documentType"] == "ESTIMATE / CASH MEMO"
    assert b["totalTax"] == 0
    assert b["cgst"] == 0 and b["sgst"] == 0 and b["igst"] == 0
    taxable = b["taxableAmount"]
    expected = round(taxable)
    assert b["grandTotal"] == expected
    assert abs(taxable - (b["grandTotal"] - b.get("roundOff", 0))) < 0.51
    # item-level gstRate retained even when disabled
    assert b["items"][0]["gstRate"] == 18
    return b


# --- Billing: includeGst=true intra-state 27 (CGST+SGST) ---
def test_billing_gst_intra_state(admin, base_url, grinding):
    payload = {
        "items": [_line(grinding, 2)],
        "paymentMode": "Cash",
        "amountReceived": 5000,
        "store": "Store 1",
        "stateCode": "27",
        "includeGst": True,
        "idempotencyKey": f"gst27-{uuid.uuid4().hex}",
    }
    r = admin.post(f"{base_url}/api/billing", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["documentType"] == "TAX INVOICE"
    assert b["includeGst"] is True
    assert b["cgst"] > 0 and b["sgst"] > 0
    assert abs(b["cgst"] - b["sgst"]) < 0.05
    assert b["igst"] == 0
    taxable = b["taxableAmount"]
    assert abs(b["cgst"] - round(taxable * 0.09, 2)) < 0.5
    assert b["items"][0]["gstRate"] == 18


# --- Billing: includeGst=true inter-state 24 (IGST) ---
def test_billing_gst_inter_state(admin, base_url, grinding):
    payload = {
        "items": [_line(grinding, 1)],
        "paymentMode": "Cash",
        "amountReceived": 5000,
        "store": "Store 1",
        "stateCode": "24",
        "includeGst": True,
        "idempotencyKey": f"gst24-{uuid.uuid4().hex}",
    }
    r = admin.post(f"{base_url}/api/billing", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["documentType"] == "TAX INVOICE"
    assert b["igst"] > 0
    assert b["cgst"] == 0 and b["sgst"] == 0
    taxable = b["taxableAmount"]
    assert abs(b["igst"] - round(taxable * 0.18, 2)) < 0.5


def _pdf_text(content: bytes) -> str:
    if not fitz:
        return ""
    doc = fitz.open(stream=content, filetype="pdf")
    txt = "\n".join(page.get_text() for page in doc)
    doc.close()
    return txt


@pytest.mark.parametrize("fmt", ["thermal", "a4", "a5"])
def test_billing_pdf_non_gst(admin, base_url, grinding, fmt):
    payload = {
        "items": [_line(grinding, 1)],
        "paymentMode": "Cash", "amountReceived": 500, "store": "Store 1", "stateCode": "27",
        "idempotencyKey": f"pdf-nogst-{fmt}-{uuid.uuid4().hex}",
    }
    b = admin.post(f"{base_url}/api/billing", json=payload, timeout=30).json()
    r = admin.get(f"{base_url}/api/billing/{b['id']}/pdf", params={"format": fmt}, timeout=60)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content.startswith(b"%PDF")
    if fitz:
        txt = _pdf_text(r.content).upper()
        assert "ESTIMATE" in txt or "CASH MEMO" in txt
        assert "CGST" not in txt
        assert "GSTIN" not in txt


@pytest.mark.parametrize("fmt", ["thermal", "a4", "a5"])
def test_billing_pdf_gst(admin, base_url, grinding, fmt):
    payload = {
        "items": [_line(grinding, 1)],
        "paymentMode": "Cash", "amountReceived": 500, "store": "Store 1", "stateCode": "27",
        "includeGst": True,
        "idempotencyKey": f"pdf-gst-{fmt}-{uuid.uuid4().hex}",
    }
    b = admin.post(f"{base_url}/api/billing", json=payload, timeout=30).json()
    r = admin.get(f"{base_url}/api/billing/{b['id']}/pdf", params={"format": fmt}, timeout=60)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    if fitz:
        txt = _pdf_text(r.content).upper()
        assert "TAX INVOICE" in txt
        assert "GSTIN" in txt
        assert "CGST" in txt or "IGST" in txt


# --- Quotation: no GST then flip to GST via PUT then convert ---
def test_quotation_gst_flip_and_convert(admin, base_url, grinding):
    payload = {
        "items": [_line(grinding, 4)],
        "customerName": f"TEST_QT_{uuid.uuid4().hex[:6]}",
        "customerPhone": "9990001111",
        "stateCode": "27",
        "validityDays": 15,
    }
    r = admin.post(f"{base_url}/api/quotations", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    q = r.json()
    assert q["includeGst"] is False
    assert q["totalTax"] == 0
    q_id = q["id"]

    # Flip to GST
    r2 = admin.put(f"{base_url}/api/quotations/{q_id}", json={"includeGst": True}, timeout=30)
    assert r2.status_code == 200
    q2 = r2.json()
    assert q2["includeGst"] is True
    assert q2["cgst"] > 0 and q2["sgst"] > 0

    # Accept
    r3 = admin.put(f"{base_url}/api/quotations/{q_id}", json={"status": "accepted"}, timeout=30)
    assert r3.status_code == 200
    assert r3.json()["status"] == "accepted"

    # Convert
    r4 = admin.post(f"{base_url}/api/quotations/{q_id}/convert", json={"paymentMode": "Cash"}, timeout=30)
    assert r4.status_code == 200, r4.text
    bill = r4.json()
    assert bill["includeGst"] is True
    assert bill["documentType"] == "TAX INVOICE"

    # Double convert
    r5 = admin.post(f"{base_url}/api/quotations/{q_id}/convert", json={"paymentMode": "Cash"}, timeout=30)
    assert r5.status_code == 400

    # PDF
    r6 = admin.get(f"{base_url}/api/quotations/{q_id}/pdf", timeout=60)
    assert r6.status_code == 200
    assert r6.content.startswith(b"%PDF")


# --- Held bills with includeGst true ---
def test_held_bill_with_include_gst(admin, base_url, grinding):
    payload = {
        "items": [_line(grinding, 2)],
        "paymentMode": "Cash",
        "store": "Store 1",
        "stateCode": "27",
        "includeGst": True,
    }
    r = admin.post(f"{base_url}/api/billing/held", json=payload, timeout=30)
    assert r.status_code == 200
    held = r.json()
    held_id = held["id"]
    assert held.get("draft", {}).get("includeGst") is True

    r2 = admin.get(f"{base_url}/api/billing/held", timeout=30)
    assert r2.status_code == 200
    row = next((x for x in r2.json() if x["id"] == held_id), None)
    assert row is not None
    assert row["draft"]["includeGst"] is True

    r3 = admin.delete(f"{base_url}/api/billing/held/{held_id}", timeout=30)
    assert r3.status_code == 200


# --- Regression: catalogue, reports, settings ---
def test_regression_products_reports_settings(admin, base_url):
    r = admin.get(f"{base_url}/api/products", params={"all": "true", "perPage": 1000}, timeout=60)
    assert r.status_code == 200
    assert r.json()["total"] >= 506

    for path in ("overview", "gst", "sales"):
        rr = admin.get(f"{base_url}/api/reports/{path}", timeout=30)
        assert rr.status_code == 200, rr.text

    s = admin.get(f"{base_url}/api/settings", timeout=30)
    assert s.status_code == 200
    p = admin.put(f"{base_url}/api/settings", json={"printFormat": s.json().get("printFormat", "thermal")}, timeout=30)
    assert p.status_code == 200
