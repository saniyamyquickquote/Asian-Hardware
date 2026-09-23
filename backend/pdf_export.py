"""Branded A4/A5 and 80 mm PDF documents for saved transactions."""
from datetime import datetime
from io import BytesIO
from textwrap import wrap
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A5
from reportlab.pdfgen import canvas

INK = colors.HexColor('#14222c')
MUTED = colors.HexColor('#657482')
AMBER = colors.HexColor('#e5a120')
LINE = colors.HexColor('#dce2e5')
MM = 72 / 25.4
IST = ZoneInfo('Asia/Kolkata')


def amount_words(number):
    ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
    tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']
    def under_thousand(n):
        bits = []
        if n >= 100:
            bits += [ones[n // 100], 'Hundred']
            n %= 100
        if n >= 20:
            bits.append(tens[n // 10]); n %= 10
        if n:
            bits.append(ones[n])
        return ' '.join(bits)
    n = int(number)
    if n == 0:
        return 'Zero Rupees Only'
    parts = []
    for scale, label in ((10000000, 'Crore'), (100000, 'Lakh'), (1000, 'Thousand'), (1, '')):
        if n >= scale:
            count, n = divmod(n, scale)
            parts += [under_thousand(count), label] if label else [under_thousand(count)]
    return ' '.join(parts) + ' Rupees Only'


def safe_text(text):
    return str(text or '').encode('latin-1', 'replace').decode('latin-1')


def draw_logo(pdf, x, y):
    pdf.setStrokeColor(INK); pdf.setLineWidth(3)
    path = pdf.beginPath(); path.moveTo(x, y - 7); path.lineTo(x + 17, y + 5); path.lineTo(x + 34, y - 7)
    pdf.drawPath(path)
    for i, color in enumerate(('#e94d47', '#2c77cf', '#39aa70', '#f3ae32')):
        pdf.setFillColor(colors.HexColor(color)); pdf.rect(x + 7 + i * 5.6, y - 23, 4.2, 16, fill=1, stroke=0)


def draw_a4(pdf, doc, setting, kind, page_size):
    width, height = page_size; left = 43; right = width - 43
    name = setting.get('storeName', 'Asian Hardware and Paints').upper()
    date = datetime.fromisoformat(doc['date']).astimezone(IST).strftime('%d/%m/%Y')
    title = 'TAX INVOICE' if kind == 'bill' else 'QUOTATION'
    def header():
        pdf.setFillColor(INK); pdf.rect(0, height - 8, width, 8, fill=1, stroke=0)
        draw_logo(pdf, left, height - 51)
        pdf.setFillColor(INK); pdf.setFont('Helvetica-Bold', 13 if width > 500 else 10)
        pdf.drawString(left + 47, height - 43, safe_text(name))
        pdf.setFont('Helvetica', 8); pdf.setFillColor(MUTED)
        pdf.drawString(left + 47, height - 56, safe_text(setting.get('address1', ''))[:85])
        pdf.drawString(left + 47, height - 68, f"Phone: {setting.get('phone1', '')}  |  GSTIN: {setting.get('gstin', '')}")
        pdf.setStrokeColor(LINE); pdf.line(left, height - 86, right, height - 86)
    header(); y = height - 114
    pdf.setFont('Helvetica-Bold', 16); pdf.setFillColor(INK); pdf.drawString(left, y, title)
    pdf.setFont('Helvetica-Bold', 9); pdf.drawRightString(right, y + 2, safe_text(doc['number']))
    y -= 23
    pdf.setFont('Helvetica', 9); pdf.setFillColor(MUTED)
    pdf.drawString(left, y, f'Date: {date}')
    if kind == 'quotation':
        pdf.drawRightString(right, y, f"Valid until: {datetime.fromisoformat(doc['validUntil']).astimezone(IST).strftime('%d/%m/%Y')}")
    else:
        pdf.drawRightString(right, y, f"Place of supply: {doc.get('placeOfSupply', 'Maharashtra (27)')}")
    y -= 25
    pdf.setFillColor(colors.HexColor('#f1f4f5')); pdf.roundRect(left, y - 42, right - left, 52, 4, fill=1, stroke=0)
    pdf.setFillColor(MUTED); pdf.setFont('Helvetica-Bold', 8); pdf.drawString(left + 12, y - 5, 'BILL TO' if kind == 'bill' else 'QUOTATION FOR')
    pdf.setFillColor(INK); pdf.setFont('Helvetica-Bold', 10); pdf.drawString(left + 12, y - 20, safe_text(doc.get('customerName') or 'Walk-in Customer')[:55])
    pdf.setFont('Helvetica', 8); pdf.drawString(left + 12, y - 33, safe_text((doc.get('customerAddress') or '') + ('  |  GSTIN: ' + doc['customerGstin'] if doc.get('customerGstin') else ''))[:100])
    y -= 66
    def table_header(y):
        pdf.setFillColor(INK); pdf.rect(left, y - 9, right - left, 22, fill=1, stroke=0)
        pdf.setFillColor(colors.white); pdf.setFont('Helvetica-Bold', 8)
        pdf.drawString(left + 8, y, '#  ITEM / HSN')
        pdf.drawRightString(right - 205, y, 'QTY')
        pdf.drawRightString(right - 158, y, 'RATE')
        pdf.drawRightString(right - 90, y, 'TAXABLE')
        pdf.drawRightString(right - 51, y, 'GST')
        pdf.drawRightString(right - 8, y, 'AMOUNT')
        return y - 26
    y = table_header(y)
    for index, item in enumerate(doc['items'], 1):
        if y < 185:
            pdf.showPage(); header(); y = table_header(height - 116)
        pdf.setFillColor(INK); pdf.setFont('Helvetica', 8)
        text = safe_text(f"{index}. {item['productName']}")
        max_chars = 42 if width > 500 else 25
        lines = wrap(text, max_chars, break_long_words=True)[:2] or [text]
        pdf.drawString(left + 8, y, lines[0])
        if len(lines) > 1:
            pdf.drawString(left + 19, y - 10, lines[1])
        if item.get('hsnCode'):
            pdf.setFont('Helvetica', 7); pdf.setFillColor(MUTED)
            pdf.drawString(left + 19, y - (20 if len(lines) > 1 else 10), f"HSN {item['hsnCode']}")
        pdf.setFillColor(INK); pdf.setFont('Helvetica', 8)
        pdf.drawRightString(right - 205, y, str(item['quantity']))
        pdf.drawRightString(right - 158, y, f"{item['unitPrice']:,.2f}")
        pdf.drawRightString(right - 90, y, f"{item['taxableAmount']:,.2f}")
        pdf.drawRightString(right - 51, y, f"{item['gstRate']:g}%")
        pdf.drawRightString(right - 8, y, f"{item['totalAmount']:,.2f}")
        step = 36 if len(lines) > 1 else 29
        pdf.setStrokeColor(LINE); pdf.line(left, y - step + 14, right, y - step + 14)
        y -= step
    if y < 190:
        pdf.showPage(); header(); y = height - 120
    y -= 11
    def total(label, value, bold=False):
        nonlocal y
        pdf.setFillColor(INK if bold else MUTED); pdf.setFont('Helvetica-Bold' if bold else 'Helvetica', 9 if bold else 8)
        pdf.drawRightString(right - 105, y, label)
        pdf.drawRightString(right - 6, y, f"Rs. {value:,.2f}")
        y -= 17
    total('Subtotal', doc['subtotal'])
    if doc.get('discountAmount'):
        total('Discount', -doc['discountAmount'])
    total('Taxable value', doc['taxableAmount'])
    if doc.get('igst'):
        total('IGST', doc['igst'])
    else:
        total('CGST', doc.get('cgst', 0)); total('SGST', doc.get('sgst', 0))
    if kind == 'bill':
        total('Round off', doc.get('roundOff', 0))
    pdf.setStrokeColor(AMBER); pdf.setLineWidth(1.5); pdf.line(right - 220, y + 5, right, y + 5)
    y -= 9; total('GRAND TOTAL', doc['grandTotal'], True)
    pdf.setFont('Helvetica-Oblique', 8); pdf.setFillColor(MUTED)
    pdf.drawString(left, y - 5, safe_text(amount_words(doc['grandTotal']))[:100]); y -= 28
    if kind == 'bill':
        pdf.setFont('Helvetica', 8); pdf.drawString(left, y, f"Payment: {doc['paymentMode']}  |  Received: Rs. {doc['amountReceived']:,.2f}  |  Change: Rs. {doc['changeReturned']:,.2f}")
    else:
        pdf.setFont('Helvetica-Bold', 8); pdf.drawString(left, y, 'TERMS & CONDITIONS'); y -= 12
        for line in wrap(safe_text(doc.get('terms') or setting.get('quotationTerms', '')), 105 if width > 500 else 68)[:4]:
            pdf.setFont('Helvetica', 8); pdf.drawString(left, y, line); y -= 11
        pdf.setFont('Helvetica-Oblique', 8); pdf.drawString(left, y - 8, 'This is a quotation, not a tax invoice.')
    pdf.setStrokeColor(LINE); pdf.line(left, 82, right, 82)
    pdf.setFont('Helvetica-Bold', 8); pdf.setFillColor(INK); pdf.drawRightString(right, 63, 'For Asian Hardware and Paints')
    pdf.setFont('Helvetica', 8); pdf.setFillColor(MUTED); pdf.drawRightString(right, 50, 'Authorized Signatory')
    pdf.drawString(left, 48, safe_text(setting.get('footerMessage', 'Thank you for shopping with us!'))[:64])


def draw_thermal(pdf, doc, setting, height):
    width = 80 * MM; x = 10; right = width - 10; y = height - 16
    def center(text, size=8, bold=False, gap=12):
        nonlocal y
        pdf.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
        pdf.drawCentredString(width / 2, y, safe_text(text)); y -= gap
    def row(label, value, bold=False):
        nonlocal y
        pdf.setFont('Helvetica-Bold' if bold else 'Helvetica', 8)
        pdf.drawString(x, y, safe_text(label)); pdf.drawRightString(right, y, safe_text(value)); y -= 13
    def divider():
        nonlocal y
        pdf.setStrokeColor(MUTED); pdf.setLineWidth(.5); pdf.line(x, y, right, y); y -= 12
    center(setting.get('storeName', 'Asian Hardware and Paints').upper(), 10, True, 14)
    for address in wrap(setting.get('address1', ''), 40)[:2]:
        center(address, 7, gap=10)
    center(f"Ph: {setting.get('phone1', '')}", 7, gap=10)
    center(f"GSTIN: {setting.get('gstin', '')}", 7, gap=10)
    divider(); center('TAX INVOICE', 10, True, 15)
    row('Bill no.', doc['number']); row('Date', datetime.fromisoformat(doc['date']).astimezone(IST).strftime('%d/%m/%Y %H:%M'))
    row('Customer', (doc.get('customerName') or 'Walk-in')[:22]); divider()
    row('ITEM / HSN', 'QTY    RATE    AMT', True); divider()
    for item in doc['items']:
        for line in wrap(item['productName'], 37, break_long_words=True)[:2]:
            row(line, '')
        row(f"{item['quantity']} x {item['unitPrice']:.2f}  GST {item['gstRate']:g}%", f"{item['totalAmount']:.2f}")
    divider()
    row('Subtotal', f"Rs. {doc['subtotal']:.2f}")
    if doc['discountAmount']:
        row('Discount', f"-Rs. {doc['discountAmount']:.2f}")
    if doc['igst']:
        row('IGST', f"Rs. {doc['igst']:.2f}")
    else:
        row('CGST', f"Rs. {doc['cgst']:.2f}"); row('SGST', f"Rs. {doc['sgst']:.2f}")
    row('Round off', f"Rs. {doc['roundOff']:+.2f}")
    divider(); row('TOTAL', f"Rs. {doc['grandTotal']:.2f}", True)
    row('Payment', doc['paymentMode'])
    if doc['paymentMode'] == 'Cash':
        row('Received', f"Rs. {doc['amountReceived']:.2f}"); row('Change', f"Rs. {doc['changeReturned']:.2f}")
    divider(); center('Thank you for shopping with us!', 8, True); center('Visit again!', 8)


def render_document(doc, setting, kind, format='a4'):
    output = BytesIO()
    if format == 'thermal' and kind == 'bill':
        # Size adjusts to item count and wrapping, avoiding clipped receipts.
        item_height = sum(30 + (12 if len(item['productName']) > 37 else 0) for item in doc['items'])
        height = max(130 * MM, 380 + item_height + (14 if doc.get('discountAmount') else 0))
        pdf = canvas.Canvas(output, pagesize=(80 * MM, height))
        draw_thermal(pdf, doc, setting, height)
    else:
        size = A5 if format == 'a5' else A4
        pdf = canvas.Canvas(output, pagesize=size)
        draw_a4(pdf, doc, setting, kind, size)
    pdf.setTitle(f"{kind.title()} {doc['number']}")
    pdf.save()
    return output.getvalue()