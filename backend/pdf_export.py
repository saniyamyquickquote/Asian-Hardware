"""Estimate / tax invoice / quotation PDFs in 80 mm thermal and A4/A5 formats."""
from datetime import datetime
from io import BytesIO
from pathlib import Path
from textwrap import wrap
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A5
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

INK = colors.HexColor('#0F172A')
INK2 = colors.HexColor('#334155')
MUTED = colors.HexColor('#64748B')
BLUE = colors.HexColor('#2563EB')
AMBER = colors.HexColor('#D97706')
LINE = colors.HexColor('#E2E8F0')
SOFT = colors.HexColor('#F8FAFC')
MM = 72 / 25.4
IST = ZoneInfo('Asia/Kolkata')
FONT_DIR = Path(__file__).parent / 'fonts'
_devanagari_cache = {}


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


def fmt(value):
    return f"{float(value or 0):,.2f}"


def doc_gst(doc):
    return bool(doc.get('includeGst', doc.get('totalTax', 0) > 0))


def doc_title(doc, kind):
    if kind == 'quotation':
        return 'QUOTATION'
    return 'TAX INVOICE' if doc_gst(doc) else 'ESTIMATE / CASH MEMO'


def local_date(value, with_time=False):
    return datetime.fromisoformat(value).astimezone(IST).strftime('%d/%m/%Y  %I:%M %p' if with_time else '%d/%m/%Y')


def gst_rate_label(doc):
    rates = {float(item.get('gstRate', 0)) for item in doc['items']}
    return f" @ {rates.pop():g}%" if len(rates) == 1 else ''


def devanagari_image(text, px=72):
    if text not in _devanagari_cache:
        font = ImageFont.truetype(str(FONT_DIR / 'NotoSansDevanagari-Bold.ttf'), px, layout_engine=ImageFont.Layout.RAQM)
        left, top, right, bottom = font.getbbox(text)
        image = Image.new('RGBA', (right - left + 8, bottom - top + 8), (0, 0, 0, 0))
        ImageDraw.Draw(image).text((4 - left, 4 - top), text, font=font, fill=(217, 119, 6, 255))
        _devanagari_cache[text] = image
    return _devanagari_cache[text]


def draw_devanagari(pdf, text, x, y, height):
    if not text:
        return 0
    image = devanagari_image(text)
    width = image.width * height / image.height
    pdf.drawImage(ImageReader(image), x, y, width, height, mask='auto')
    return width


def draw_logo(pdf, x, y):
    pdf.setStrokeColor(INK); pdf.setLineWidth(3); pdf.setLineJoin(1)
    path = pdf.beginPath(); path.moveTo(x, y - 7); path.lineTo(x + 17, y + 5); path.lineTo(x + 34, y - 7)
    pdf.drawPath(path)
    for i, color in enumerate(('#e94d47', '#2c77cf', '#39aa70', '#f3ae32')):
        pdf.setFillColor(colors.HexColor(color)); pdf.roundRect(x + 7 + i * 5.6, y - 23, 4.2, 16, 1, fill=1, stroke=0)


def draw_a4(pdf, doc, setting, kind, page_size):
    width, height = page_size
    a4 = width > 500
    k = 1 if a4 else 0.72
    margin = 28 if a4 else 18
    left = margin + 16; right = width - margin - 16
    gst = doc_gst(doc)
    title = doc_title(doc, kind)
    body = 8.5 if a4 else 7.4
    name_chars = (40 if gst else 58) if a4 else (26 if gst else 38)

    def frame():
        pdf.setStrokeColor(LINE); pdf.setLineWidth(1)
        pdf.roundRect(margin, margin, width - 2 * margin, height - 2 * margin, 12, fill=0, stroke=1)
        pdf.setFillColor(BLUE); pdf.roundRect(margin + 12, height - margin - 2.5, width - 2 * margin - 24, 3, 1.5, fill=1, stroke=0)

    def header():
        frame()
        top = height - margin - 30
        draw_logo(pdf, left, top - 2)
        pdf.setFillColor(INK); pdf.setFont('Helvetica-Bold', 14 if a4 else 10.5)
        pdf.drawString(left + 46, top - 6, safe_text(setting.get('storeName', 'Asian Hardware and Paints')).upper())
        draw_devanagari(pdf, setting.get('storeNameMarathi', ''), left + 46, top - 25, 12 if a4 else 9)
        pdf.setFont('Helvetica', 7.5 if a4 else 6.5); pdf.setFillColor(MUTED)
        pdf.drawString(left + 46, top - 37, safe_text(setting.get('address1', ''))[:95])
        phones = '  |  '.join(f"+91 {p}" for p in (setting.get('phone1'), setting.get('phone2')) if p)
        pdf.drawString(left + 46, top - 48, f"Ph: {phones}")
        if gst:
            pdf.setFont('Helvetica-Bold', 7.5 if a4 else 6.5); pdf.setFillColor(INK2)
            pdf.drawString(left + 46, top - 59, f"GSTIN: {setting.get('gstin', '')}")
        pdf.setFillColor(INK); pdf.setFont('Helvetica-Bold', 15 if a4 else 10.5)
        pdf.drawRightString(right, top - 6, title)
        pdf.setFont('Helvetica-Bold', 9.5 if a4 else 8); pdf.setFillColor(BLUE)
        pdf.drawRightString(right, top - 22, safe_text(doc['number']))
        pdf.setFont('Helvetica', 7.5 if a4 else 6.5); pdf.setFillColor(MUTED)
        pdf.drawRightString(right, top - 36, f"Date: {local_date(doc['date'])}")
        if kind == 'quotation':
            pdf.drawRightString(right, top - 47, f"Valid until: {local_date(doc['validUntil'])}  ({doc.get('validityDays', 7)} days)")
        elif gst:
            pdf.drawRightString(right, top - 47, f"Place of supply: {doc.get('placeOfSupply', 'Maharashtra (27)')}")
        pdf.setStrokeColor(LINE); pdf.setLineWidth(1); pdf.line(left, top - 70, right, top - 70)
        return top - 92

    def customer_box(y):
        pdf.setFillColor(SOFT); pdf.setStrokeColor(LINE)
        pdf.roundRect(left, y - 44, right - left, 56, 8, fill=1, stroke=1)
        pdf.setFillColor(MUTED); pdf.setFont('Helvetica-Bold', 7)
        pdf.drawString(left + 14, y - 2, 'BILL TO' if kind == 'bill' else 'QUOTATION FOR')
        pdf.setFillColor(INK); pdf.setFont('Helvetica-Bold', 10.5 if a4 else 9)
        pdf.drawString(left + 14, y - 17, safe_text(doc.get('customerName') or 'Walk-in Customer')[:60])
        details = [d for d in (doc.get('customerPhone'), doc.get('customerAddress')) if d]
        if gst and doc.get('customerGstin'):
            details.append(f"GSTIN {doc['customerGstin']}")
        pdf.setFont('Helvetica', 7.5 if a4 else 6.5); pdf.setFillColor(INK2)
        pdf.drawString(left + 14, y - 31, safe_text('  |  '.join(details))[:110])
        if kind == 'bill':
            pdf.setFont('Helvetica-Bold', 7.5); pdf.setFillColor(MUTED)
            pdf.drawRightString(right - 14, y - 17, f"{doc.get('store', 'Store 1')}  ·  {doc.get('paymentMode', 'Cash').upper()}")
        return y - 66

    cols = ({'qty': 228, 'rate': 172, 'taxable': 104, 'gst': 62, 'amt': 10} if gst else {'qty': 210, 'rate': 120, 'amt': 10})
    cols = {key: right - value * k for key, value in cols.items()}

    def table_header(y):
        pdf.setFillColor(INK); pdf.roundRect(left, y - 9, right - left, 22, 5, fill=1, stroke=0)
        pdf.setFillColor(colors.white); pdf.setFont('Helvetica-Bold', 7.5)
        pdf.drawString(left + 10, y, '#')
        pdf.drawString(left + 28, y, 'ITEM / HSN' if gst else 'ITEM')
        pdf.drawRightString(cols['qty'], y, 'QTY')
        pdf.drawRightString(cols['rate'], y, 'RATE')
        if gst:
            pdf.drawRightString(cols['taxable'], y, 'TAXABLE')
            pdf.drawRightString(cols['gst'], y, 'GST')
        pdf.drawRightString(cols['amt'], y, 'AMOUNT')
        return y - 27

    y = customer_box(header())
    y = table_header(y)
    for index, item in enumerate(doc['items'], 1):
        lines = wrap(safe_text(item['productName']), name_chars, break_long_words=True)[:2] or ['']
        if item.get('remarks'):
            lines.append(safe_text(item['remarks'])[:name_chars])
        extra = (10 if len(lines) > 1 else 0) + (10 if len(lines) > 2 else 0) + (9 if gst and item.get('hsnCode') else 0)
        step = 24 + extra
        if y - step < margin + 150:
            pdf.showPage(); y = table_header(header())
        if index % 2 == 0:
            pdf.setFillColor(SOFT); pdf.rect(left, y - step + 12, right - left, step, fill=1, stroke=0)
        pdf.setFillColor(MUTED); pdf.setFont('Helvetica', body)
        pdf.drawString(left + 10, y, str(index))
        pdf.setFillColor(INK); pdf.setFont('Helvetica-Bold' if index == 0 else 'Helvetica', body)
        row_y = y
        for line_index, line in enumerate(lines):
            pdf.setFillColor(INK if line_index < 2 else MUTED)
            pdf.setFont('Helvetica' if line_index < 2 else 'Helvetica-Oblique', body if line_index < 2 else body - 1)
            pdf.drawString(left + 28, row_y, line); row_y -= 10
        if gst and item.get('hsnCode'):
            pdf.setFont('Helvetica', body - 1.5); pdf.setFillColor(MUTED)
            pdf.drawString(left + 28, row_y, f"HSN {item['hsnCode']}")
        pdf.setFillColor(INK); pdf.setFont('Helvetica', body)
        pdf.drawRightString(cols['qty'], y, f"{item['quantity']} {'pcs' if item.get('unit', 'Piece') == 'Piece' else item['unit'][:5]}")
        pdf.drawRightString(cols['rate'], y, fmt(item['unitPrice']))
        if gst:
            pdf.drawRightString(cols['taxable'], y, fmt(item['taxableAmount']))
            pdf.drawRightString(cols['gst'], y, f"{item['gstRate']:g}%")
        pdf.setFont('Helvetica-Bold', body)
        pdf.drawRightString(cols['amt'], y, fmt(item['totalAmount']))
        pdf.setStrokeColor(LINE); pdf.setLineWidth(.5); pdf.line(left, y - step + 12, right, y - step + 12)
        y -= step
    if y < margin + 190:
        pdf.showPage(); y = header()
    y -= 14
    totals_left = right - 215 * k

    def total(label, value, bold=False, color=None):
        nonlocal y
        pdf.setFillColor(color or (INK if bold else INK2)); pdf.setFont('Helvetica-Bold' if bold else 'Helvetica', 10 if bold else body)
        pdf.drawString(totals_left, y, label)
        pdf.drawRightString(right - 10, y, f"Rs. {fmt(value)}" if value >= 0 else f"- Rs. {fmt(-value)}")
        y -= 18 if bold else 15

    total('Subtotal', doc['subtotal'])
    if doc.get('discountAmount'):
        total('Discount', -doc['discountAmount'], color=AMBER)
    if gst:
        total('Taxable Value', doc['taxableAmount'])
        if doc.get('igst'):
            total(f"IGST{gst_rate_label(doc)}", doc['igst'])
        else:
            half = gst_rate_label(doc)
            half = f" @ {float(half.split('@')[1].strip('% ')) / 2:g}%" if half else ''
            total(f"CGST{half}", doc.get('cgst', 0)); total(f"SGST{half}", doc.get('sgst', 0))
    if kind == 'bill' and doc.get('roundOff'):
        total('Round Off', doc['roundOff'])
    pdf.setStrokeColor(AMBER); pdf.setLineWidth(1.5); pdf.line(totals_left, y + 6, right, y + 6)
    y -= 8
    total('GRAND TOTAL', doc['grandTotal'], True)
    pdf.setFont('Helvetica-Oblique', 7.5); pdf.setFillColor(MUTED)
    pdf.drawString(left, y + 4, safe_text(amount_words(doc['grandTotal']))[:110])
    y -= 22
    if kind == 'bill':
        pdf.setFont('Helvetica', body); pdf.setFillColor(INK2)
        if doc['paymentMode'] == 'Cash':
            line = f"Payment Mode: CASH   |   Received: Rs. {fmt(doc['amountReceived'])}   |   Change: Rs. {fmt(doc['changeReturned'])}"
        elif doc['paymentMode'] in ('Credit', 'Mixed'):
            line = f"Payment Mode: {'KHATA / CREDIT' if doc['paymentMode'] == 'Credit' else 'MIXED'}   |   Paid: Rs. {fmt(doc['amountReceived'])}   |   Balance due: Rs. {fmt(doc.get('dueAmount', 0))}"
        else:
            line = f"Payment Mode: {doc['paymentMode'].upper()}" + (f"   |   Ref: {doc['upiTransactionId']}" if doc.get('upiTransactionId') else '')
        pdf.drawString(left, y, line)
    else:
        terms = wrap(safe_text(doc.get('terms') or setting.get('quotationTerms', '')), 118 if a4 else 78)[:4]
        box_height = 30 + 11 * len(terms)
        pdf.setFillColor(SOFT); pdf.setStrokeColor(LINE); pdf.roundRect(left, y - box_height + 12, right - left, box_height, 8, fill=1, stroke=1)
        pdf.setFillColor(MUTED); pdf.setFont('Helvetica-Bold', 7); pdf.drawString(left + 12, y, 'TERMS & CONDITIONS')
        pdf.setFillColor(INK2); pdf.setFont('Helvetica', body - .5)
        for line in terms:
            y -= 11; pdf.drawString(left + 12, y, line)
        y -= 20
        pdf.setFont('Helvetica-Oblique', 7); pdf.setFillColor(MUTED)
        pdf.drawString(left, y, 'This is a quotation, not a tax invoice.')
    base = margin + 18
    pdf.setStrokeColor(LINE); pdf.setLineWidth(1); pdf.line(left, base + 58, right, base + 58)
    pdf.setStrokeColor(INK2); pdf.line(right - 150 * k, base + 22, right, base + 22)
    pdf.setFont('Helvetica-Bold', 7.5); pdf.setFillColor(INK)
    pdf.drawRightString(right, base + 44, f"For {setting.get('storeName', 'Asian Hardware and Paints')}")
    pdf.setFont('Helvetica', 7.5); pdf.setFillColor(MUTED); pdf.drawRightString(right, base + 10, 'Authorized Signatory')
    pdf.setFont('Helvetica-Bold', 8.5); pdf.setFillColor(INK)
    pdf.drawString(left, base + 40, safe_text(setting.get('footerMessage', 'Thank you for shopping with us!') if kind == 'bill' else 'Thank you for the opportunity to quote.')[:70])
    pdf.setFont('Helvetica', 7); pdf.setFillColor(MUTED)
    pdf.drawString(left, base + 26, 'Goods once sold will not be taken back or exchanged.' if kind == 'bill' else 'We look forward to working with you.')


def draw_thermal(pdf, doc, setting, height):
    width = 80 * MM; x = 9; right = width - 9; y = height - 18
    gst = doc_gst(doc)
    col_qty, col_rate = right - 92, right - 50

    def center(text, size=8, bold=False, gap=12):
        nonlocal y
        pdf.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
        pdf.drawCentredString(width / 2, y, safe_text(text)); y -= gap

    def row(label, value, bold=False, size=8, gap=13):
        nonlocal y
        pdf.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
        pdf.drawString(x, y, safe_text(label)); pdf.drawRightString(right, y, safe_text(value)); y -= gap

    def rule(thick=False):
        nonlocal y
        pdf.setStrokeColor(INK if thick else MUTED); pdf.setLineWidth(1.2 if thick else .5)
        pdf.setDash([] if thick else [2, 2]); pdf.line(x, y + 4, right, y + 4); pdf.setDash([]); y -= 11

    pdf.setFillColor(INK)
    center(setting.get('storeName', 'Asian Hardware and Paints').upper(), 10.5, True, 14)
    for line in wrap(setting.get('address1', ''), 42)[:2]:
        center(line, 7, gap=10)
    center(f"Ph: +91 {setting.get('phone1', '')}", 7, gap=10)
    if gst:
        center(f"GSTIN: {setting.get('gstin', '')}", 7.5, True, 11)
    rule(True)
    center('TAX INVOICE' if gst else 'ESTIMATE / RETAIL BILL', 9.5, True, 15)
    pdf.setFont('Helvetica', 7.5)
    pdf.drawString(x, y, f"Bill No: {doc['number']}"); y -= 11
    pdf.drawString(x, y, f"Date: {local_date(doc['date'], True)}"); y -= 11
    pdf.drawString(x, y, safe_text(f"Customer: {doc.get('customerName') or 'Walk-in Customer'}")[:40]); y -= 11
    if gst and doc.get('customerGstin'):
        pdf.drawString(x, y, f"Cust. GSTIN: {doc['customerGstin']}"); y -= 11
    rule(True)
    pdf.setFont('Helvetica-Bold', 7.5)
    pdf.drawString(x, y, 'Item Name'); pdf.drawRightString(col_qty, y, 'Qty'); pdf.drawRightString(col_rate, y, 'Rate'); pdf.drawRightString(right, y, 'Amount'); y -= 12
    rule()
    pieces = 0
    for item in doc['items']:
        pieces += item['quantity']
        name = safe_text(item['productName'])
        if len(name) <= 20:
            pdf.setFont('Helvetica', 8); pdf.drawString(x, y, name)
        else:
            for line in wrap(name, 40, break_long_words=True)[:2]:
                pdf.setFont('Helvetica', 8); pdf.drawString(x, y, line); y -= 11
        pdf.setFont('Helvetica', 8)
        pdf.drawRightString(col_qty, y, str(item['quantity'])); pdf.drawRightString(col_rate, y, fmt(item['unitPrice'])); pdf.drawRightString(right, y, fmt(item['totalAmount'])); y -= 11
        if gst:
            pdf.setFont('Helvetica', 6.5); pdf.setFillColor(MUTED)
            pdf.drawString(x, y, f"{'HSN ' + item['hsnCode'] + '  ·  ' if item.get('hsnCode') else ''}GST {item['gstRate']:g}%  ·  Taxable {fmt(item['taxableAmount'])}"); y -= 10
            pdf.setFillColor(INK)
        if item.get('itemDiscount'):
            pdf.setFont('Helvetica', 6.5); pdf.setFillColor(MUTED)
            pdf.drawString(x, y, f"Less discount Rs. {fmt(item['itemDiscount'])}"); y -= 10
            pdf.setFillColor(INK)
        y -= 3
    rule()
    row(f"Total Items: {len(doc['items'])} ({pieces} pcs)", '', size=7.5)
    row('Subtotal:', f"Rs. {fmt(doc['subtotal'])}")
    if doc.get('discountAmount'):
        row('Discount:', f"- Rs. {fmt(doc['discountAmount'])}")
    if gst:
        row('Taxable Value:', f"Rs. {fmt(doc['taxableAmount'])}")
        if doc.get('igst'):
            row(f"IGST{gst_rate_label(doc)}:", f"Rs. {fmt(doc['igst'])}")
        else:
            label = gst_rate_label(doc)
            half = f" @ {float(label.split('@')[1].strip('% ')) / 2:g}%" if label else ''
            row(f"CGST{half}:", f"Rs. {fmt(doc['cgst'])}"); row(f"SGST{half}:", f"Rs. {fmt(doc['sgst'])}")
    if doc.get('roundOff'):
        row('Round Off:', f"{doc['roundOff']:+.2f}")
    rule()
    row('GRAND TOTAL:', f"Rs. {fmt(doc['grandTotal'])}", True, 10, 16)
    rule()
    mode = {'Credit': 'KHATA / CREDIT', 'UPI': 'UPI / GPAY'}.get(doc['paymentMode'], doc['paymentMode'].upper())
    row('Payment Mode:', mode, size=7.5)
    if doc['paymentMode'] == 'Cash':
        row(f"Received: Rs. {fmt(doc['amountReceived'])}", f"Change: Rs. {fmt(doc['changeReturned'])}", size=7.5)
    elif doc['paymentMode'] in ('Credit', 'Mixed'):
        row(f"Paid: Rs. {fmt(doc['amountReceived'])}", f"Balance due: Rs. {fmt(doc.get('dueAmount', 0))}", size=7.5)
    elif doc.get('upiTransactionId'):
        row('Ref:', doc['upiTransactionId'][:24], size=7.5)
    rule(True)
    footer = setting.get('footerMessage', 'Thank you for shopping with us!')
    center(footer[:44], 8, True)
    if 'visit' not in footer.lower():
        center('Visit Again!', 8, gap=10)
    return y


def render_document(doc, setting, kind, format='a4'):
    output = BytesIO()
    if format == 'thermal' and kind == 'bill':
        probe_height = 4000
        used = probe_height - draw_thermal(canvas.Canvas(BytesIO(), pagesize=(80 * MM, probe_height)), doc, setting, probe_height)
        height = max(120 * MM, used + 24)
        pdf = canvas.Canvas(output, pagesize=(80 * MM, height))
        draw_thermal(pdf, doc, setting, height)
    else:
        size = A5 if format == 'a5' else A4
        pdf = canvas.Canvas(output, pagesize=size)
        draw_a4(pdf, doc, setting, kind, size)
    pdf.setTitle(f"{doc_title(doc, kind).title()} {doc['number']}")
    pdf.save()
    return output.getvalue()
