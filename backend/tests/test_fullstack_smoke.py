import os
import re
import uuid
from datetime import datetime

import pytest
import requests
from dotenv import load_dotenv


load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")
    return BASE_URL.rstrip("/")


@pytest.fixture
def api_client():
    session = requests.Session()
    return session


@pytest.fixture
def admin_session(base_url):
    session = requests.Session()
    response = session.post(
        f"{base_url}/api/auth/login",
        json={"username": "admin", "password": "asian2019"},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["username"] == "admin"
    assert "name" in body
    return session


# Public contact + auth protection checks
def test_public_inquiry_submit_ok(api_client, base_url):
    payload = {
        "name": "Test Inquiry",
        "phone": "9876543210",
        "message": f"Need quotation {uuid.uuid4().hex[:8]}",
    }
    response = api_client.post(f"{base_url}/api/inquiries", json=payload, timeout=30)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "message" in body


# Protected endpoint checks
@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/products",
        "/api/billing",
        "/api/reports/overview",
    ],
)
def test_anonymous_access_denied(api_client, base_url, endpoint):
    response = api_client.get(f"{base_url}{endpoint}", timeout=30)
    assert response.status_code == 401
    assert "detail" in response.json()


# Login/logout flow checks
def test_login_me_logout_flow(api_client, base_url):
    login = api_client.post(
        f"{base_url}/api/auth/login",
        json={"username": "admin", "password": "asian2019"},
        timeout=30,
    )
    assert login.status_code == 200
    assert login.json()["username"] == "admin"

    me = api_client.get(f"{base_url}/api/auth/me", timeout=30)
    assert me.status_code == 200
    assert me.json()["username"] == "admin"

    logout = api_client.post(f"{base_url}/api/auth/logout", timeout=30)
    assert logout.status_code == 200
    assert logout.json()["ok"] is True

    me_after = api_client.get(f"{base_url}/api/auth/me", timeout=30)
    assert me_after.status_code == 401


# Seeded product catalogue checks
def test_seeded_products_count_and_fuzzy_target(admin_session, base_url):
    products = admin_session.get(
        f"{base_url}/api/products",
        params={"all": "true", "perPage": 1000},
        timeout=60,
    )
    assert products.status_code == 200
    body = products.json()
    assert body["total"] >= 506
    assert sum(bool(re.fullmatch(r"AH-\d{5}", p.get("sku", ""))) for p in body["items"]) == 506
    assert any(p["name"] == "GRINDING WHEEL" for p in body["items"])


# Inventory CRUD + stock audit checks
def test_inventory_crud_and_adjustment_audit(admin_session, base_url):
    suffix = uuid.uuid4().hex[:6].upper()
    create_payload = {
        "name": f"TEST_ITEM_{suffix}",
        "category": "General & Misc",
        "sku": f"TEST-SKU-{suffix}",
        "salePrice": 99.0,
        "purchasePrice": 50.0,
        "gstRate": 18,
        "currentStock": 2,
    }
    created = admin_session.post(f"{base_url}/api/products", json=create_payload, timeout=30)
    assert created.status_code == 200, created.text
    product = created.json()
    assert product["name"] == create_payload["name"]
    product_id = product["id"]

    fetched = admin_session.get(f"{base_url}/api/products/{product_id}", timeout=30)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == product_id

    updated = admin_session.put(
        f"{base_url}/api/products/{product_id}",
        json={"salePrice": 111.0, "notes": "TEST_UPDATE"},
        timeout=30,
    )
    assert updated.status_code == 200
    assert updated.json()["salePrice"] == 111.0

    adjusted = admin_session.post(
        f"{base_url}/api/products/{product_id}/adjust",
        json={"newQty": 7, "reason": "Correction", "notes": "Stock check"},
        timeout=30,
    )
    assert adjusted.status_code == 200
    adjust_doc = adjusted.json()
    assert adjust_doc["newQty"] == 7

    detail = admin_session.get(f"{base_url}/api/products/{product_id}", timeout=30)
    assert detail.status_code == 200
    assert detail.json()["currentStock"] == 7
    assert any(a["id"] == adjust_doc["id"] for a in detail.json()["history"]["adjustments"])

    deleted = admin_session.delete(f"{base_url}/api/products/{product_id}", timeout=30)
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True


# CSV import/export/template smoke checks
def test_inventory_csv_export_template_import_smoke(admin_session, base_url):
    template = admin_session.get(f"{base_url}/api/products/template", timeout=30)
    assert template.status_code == 200
    assert "name" in template.text and "salePrice" in template.text

    export_data = admin_session.get(f"{base_url}/api/products/export", timeout=60)
    assert export_data.status_code == 200
    assert "sku,name,category" in export_data.text

    unique_name = f"TEST_IMPORT_{uuid.uuid4().hex[:6].upper()}"
    csv_text = (
        "sku,name,category,brand,unit,salePrice,purchasePrice,gstRate,hsnCode,currentStock,minStockLevel,location\n"
        f"IM-{uuid.uuid4().hex[:4].upper()},{unique_name},General & Misc,TestBrand,Piece,25,10,18,,3,1,Store 1\n"
    )
    files = {"file": ("import.csv", csv_text.encode("utf-8"), "text/csv")}
    imported = admin_session.post(f"{base_url}/api/products/import", files=files, timeout=60)
    assert imported.status_code == 200
    assert imported.json()["created"] >= 1

    searched = admin_session.get(
        f"{base_url}/api/products",
        params={"q": unique_name, "all": "true", "perPage": 1000},
        timeout=30,
    )
    assert searched.status_code == 200
    assert any(p["name"] == unique_name for p in searched.json()["items"])


def _get_grinding_wheel(admin_session, base_url):
    response = admin_session.get(f"{base_url}/api/products/search", params={"q": "GRINDING"}, timeout=30)
    assert response.status_code == 200
    matches = response.json()
    target = next((p for p in matches if p["name"] == "GRINDING WHEEL"), None)
    assert target is not None
    return target


# POS flow + PDF + hold/resume endpoint checks
def test_billing_hold_create_pdf_and_persistence(admin_session, base_url):
    item = _get_grinding_wheel(admin_session, base_url)
    held_payload = {
        "items": [{"productId": item["id"], "name": item["name"], "quantity": 1, "unitPrice": item["salePrice"], "discountType": "amount", "discountValue": 0, "gstRate": item["gstRate"], "remarks": ""}],
        "paymentMode": "Cash",
        "store": "Store 1",
        "stateCode": "27",
    }
    held = admin_session.post(f"{base_url}/api/billing/held", json=held_payload, timeout=30)
    assert held.status_code == 200
    held_id = held.json()["id"]

    held_list = admin_session.get(f"{base_url}/api/billing/held", timeout=30)
    assert held_list.status_code == 200
    assert any(row["id"] == held_id for row in held_list.json())

    removed = admin_session.delete(f"{base_url}/api/billing/held/{held_id}", timeout=30)
    assert removed.status_code == 200
    assert removed.json()["ok"] is True

    bill_payload = {
        "items": [
            {"productId": item["id"], "name": item["name"], "quantity": 2, "unitPrice": item["salePrice"], "discountType": "amount", "discountValue": 0, "gstRate": item["gstRate"], "remarks": ""},
            {"name": "TEST CUSTOM LINE", "quantity": 1, "unitPrice": 25, "discountType": "amount", "discountValue": 0, "gstRate": 18, "remarks": ""},
        ],
        "paymentMode": "Cash",
        "amountReceived": 1000,
        "store": "Store 1",
        "stateCode": "27",
        "idempotencyKey": f"test-{uuid.uuid4().hex}",
    }
    created = admin_session.post(f"{base_url}/api/billing", json=bill_payload, timeout=30)
    assert created.status_code == 200, created.text
    bill = created.json()
    assert re.match(r"AH/\d{4}-\d{2}/\d{5}", bill["number"])
    # Default includeGst=false → no tax lines
    assert bill["includeGst"] is False
    assert bill["cgst"] == 0 and bill["sgst"] == 0 and bill["igst"] == 0
    assert bill["grandTotal"] > 0

    fetched = admin_session.get(f"{base_url}/api/billing/{bill['id']}", timeout=30)
    assert fetched.status_code == 200
    assert fetched.json()["number"] == bill["number"]

    thermal = admin_session.get(f"{base_url}/api/billing/{bill['id']}/pdf", params={"format": "thermal"}, timeout=60)
    assert thermal.status_code == 200
    assert thermal.headers["content-type"].startswith("application/pdf")
    assert thermal.content.startswith(b"%PDF")

    a4 = admin_session.get(f"{base_url}/api/billing/{bill['id']}/pdf", params={"format": "a4"}, timeout=60)
    assert a4.status_code == 200
    assert a4.headers["content-type"].startswith("application/pdf")
    assert a4.content.startswith(b"%PDF")


# Customer, credit bill, payment, ledger checks
def test_customers_credit_bill_payment_ledger(admin_session, base_url):
    suffix = uuid.uuid4().hex[:6].upper()
    c1 = admin_session.post(
        f"{base_url}/api/customers",
        json={"name": f"TEST_CUST_A_{suffix}", "phone": "", "address": "Test", "gstin": ""},
        timeout=30,
    )
    assert c1.status_code == 200
    cust_one = c1.json()
    assert cust_one["name"].startswith("TEST_CUST_A_")

    c2 = admin_session.post(
        f"{base_url}/api/customers",
        json={"name": f"TEST_CUST_B_{suffix}", "phone": "", "address": "Test", "gstin": ""},
        timeout=30,
    )
    assert c2.status_code == 200

    item = _get_grinding_wheel(admin_session, base_url)
    bill = admin_session.post(
        f"{base_url}/api/billing",
        json={
            "items": [{"productId": item["id"], "quantity": 1, "unitPrice": item["salePrice"], "discountType": "amount", "discountValue": 0}],
            "customerId": cust_one["id"],
            "paymentMode": "Credit",
            "amountReceived": 0,
            "store": "Store 1",
            "stateCode": "27",
            "idempotencyKey": f"credit-{uuid.uuid4().hex}",
        },
        timeout=30,
    )
    assert bill.status_code == 200, bill.text
    bill_doc = bill.json()
    assert bill_doc["dueAmount"] > 0

    payment = admin_session.post(
        f"{base_url}/api/customers/{cust_one['id']}/payment",
        json={"amount": round(bill_doc["dueAmount"] / 2, 2), "mode": "Cash", "reference": "TEST-PAY"},
        timeout=30,
    )
    assert payment.status_code == 200
    assert payment.json()["mode"] == "Cash"

    detail = admin_session.get(f"{base_url}/api/customers/{cust_one['id']}", timeout=30)
    assert detail.status_code == 200
    body = detail.json()
    assert body["balance"] >= 0
    assert any(entry["type"] == "Bill" for entry in body["ledger"])
    assert any(entry["type"] == "Payment" for entry in body["ledger"])


# Quotation save/edit/status/convert checks
def test_quotation_accept_convert_once_and_pdf(admin_session, base_url):
    item = _get_grinding_wheel(admin_session, base_url)
    quote = admin_session.post(
        f"{base_url}/api/quotations",
        json={
            "items": [{"productId": item["id"], "quantity": 1, "unitPrice": item["salePrice"], "discountType": "amount", "discountValue": 0}],
            "customerName": f"TEST_QUOTE_{uuid.uuid4().hex[:6].upper()}",
            "customerPhone": "9999999999",
            "status": "draft",
            "validityDays": 7,
            "stateCode": "27",
        },
        timeout=30,
    )
    assert quote.status_code == 200, quote.text
    quote_doc = quote.json()
    assert re.match(r"QT/\d{4}-\d{2}/\d{5}", quote_doc["number"])

    accepted = admin_session.put(
        f"{base_url}/api/quotations/{quote_doc['id']}",
        json={"status": "accepted"},
        timeout=30,
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    converted = admin_session.post(
        f"{base_url}/api/quotations/{quote_doc['id']}/convert",
        json={"paymentMode": "Cash"},
        timeout=30,
    )
    assert converted.status_code == 200
    bill = converted.json()
    assert bill["sourceQuotationId"] == quote_doc["id"]

    converted_twice = admin_session.post(
        f"{base_url}/api/quotations/{quote_doc['id']}/convert",
        json={"paymentMode": "Cash"},
        timeout=30,
    )
    assert converted_twice.status_code == 400
    assert "already converted" in converted_twice.json()["detail"].lower()

    pdf = admin_session.get(f"{base_url}/api/quotations/{quote_doc['id']}/pdf", timeout=60)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF")


# Reports + settings checks
def test_reports_and_settings_print_format_roundtrip(admin_session, base_url):
    today = datetime.utcnow().date().isoformat()
    month = today[:7]

    overview = admin_session.get(f"{base_url}/api/reports/overview", timeout=30)
    assert overview.status_code == 200
    assert "todaySales" in overview.json()

    daily = admin_session.get(f"{base_url}/api/reports/daily", params={"date": today}, timeout=30)
    assert daily.status_code == 200
    assert daily.json()["date"] == today

    monthly = admin_session.get(f"{base_url}/api/reports/monthly", params={"month": month}, timeout=30)
    assert monthly.status_code == 200
    assert monthly.json()["month"] == month

    for path in ("products", "categories", "sales", "gst", "stock", "customers", "quotations"):
        response = admin_session.get(
            f"{base_url}/api/reports/{path}",
            params={"fromDate": today, "toDate": today},
            timeout=30,
        )
        assert response.status_code == 200

    settings = admin_session.get(f"{base_url}/api/settings", timeout=30)
    assert settings.status_code == 200
    old = settings.json()
    current = old.get("printFormat", "thermal")
    new_value = "a4" if current != "a4" else "thermal"

    updated = admin_session.put(f"{base_url}/api/settings", json={"printFormat": new_value}, timeout=30)
    assert updated.status_code == 200
    assert updated.json()["printFormat"] == new_value

    restored = admin_session.put(f"{base_url}/api/settings", json={"printFormat": current}, timeout=30)
    assert restored.status_code == 200
    assert restored.json()["printFormat"] == current