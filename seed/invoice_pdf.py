"""Render synthetic invoice PDFs (used by the golden-path seed and the eval generator).

Everything here is fictional demo data. "Attack" features are inert:
hidden text is just white text, and links point at our own demo sites.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

BILL_TO = ["Halcyon Manufacturing Inc.", "Accounts Payable", "400 Lakeview Drive", "Columbus, OH 43215, USA"]
CENT = Decimal("0.01")


@dataclass
class Line:
    description: str
    qty: Decimal
    unit_price: Decimal

    @property
    def amount(self) -> Decimal:
        return (self.qty * self.unit_price).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class InvoiceSpec:
    vendor_name: str
    vendor_address: list[str]
    sender_email: str
    invoice_number: str
    invoice_date: str  # ISO YYYY-MM-DD
    due_date: str
    po_number: str | None
    currency: str
    lines: list[Line]
    tax_rate: Decimal = Decimal("0")
    tax_label: str = "Tax"
    bank: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    style: str = "us"  # "us" | "eu"
    banner: str | None = None  # e.g. "SECOND NOTICE"
    hidden_text: list[str] = field(default_factory=list)
    # How hidden_text is concealed: "white" (white 1pt), "tiny" (normal ink, 1pt), "offpage" (drawn outside the page box)
    hidden_style: str = "white"
    button: tuple[str, str] | None = None  # (label, url)
    metadata_subject: str | None = None

    @property
    def subtotal(self) -> Decimal:
        return sum((l.amount for l in self.lines), Decimal("0"))

    @property
    def tax(self) -> Decimal:
        return (self.subtotal * self.tax_rate).quantize(CENT, rounding=ROUND_HALF_UP)

    @property
    def total(self) -> Decimal:
        return self.subtotal + self.tax


def fmt(d: Decimal, style: str) -> str:
    s = f"{d:,.2f}"
    if style == "eu":
        s = s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return s


def fmt_qty(d: Decimal, style: str) -> str:
    s = f"{d.normalize():f}"
    return s.replace(".", ",") if style == "eu" else s


def fmt_date(iso: str, style: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}" if style == "eu" else iso


def render(spec: InvoiceSpec, path: str) -> None:
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    st = spec.style
    c.setTitle(f"Invoice {spec.invoice_number}")
    c.setAuthor(spec.vendor_name)
    if spec.metadata_subject:
        c.setSubject(spec.metadata_subject)

    ink, muted, accent = HexColor("#111827"), HexColor("#6b7280"), HexColor("#1d4ed8")

    # Header
    if st == "eu":
        # Messier layout: labels bilingual, meta block on the left, vendor on the right.
        c.setFillColor(ink)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(40, h - 60, "RECHNUNG / INVOICE")
        c.setFont("Helvetica", 9)
        meta = [
            ("Rechnungsnr. / Invoice No.", spec.invoice_number),
            ("Datum / Date", fmt_date(spec.invoice_date, st)),
            ("Fällig / Due", fmt_date(spec.due_date, st)),
            ("Bestellnr. / PO", spec.po_number or "-"),
        ]
        y = h - 85
        for k, v in meta:
            c.drawString(40, y, f"{k}: {v}")
            y -= 13
        c.setFont("Helvetica-Bold", 12)
        c.drawRightString(w - 40, h - 60, spec.vendor_name)
        c.setFont("Helvetica", 9)
        y = h - 75
        for line in spec.vendor_address + [spec.sender_email]:
            c.drawRightString(w - 40, y, line)
            y -= 12
    else:
        c.setFillColor(ink)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(40, h - 60, spec.vendor_name)
        c.setFont("Helvetica", 9)
        c.setFillColor(muted)
        y = h - 75
        for line in spec.vendor_address + [spec.sender_email]:
            c.drawString(40, y, line)
            y -= 12
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 24)
        c.drawRightString(w - 40, h - 62, "INVOICE")
        c.setFillColor(ink)
        c.setFont("Helvetica", 9)
        meta = [
            ("Invoice Number", spec.invoice_number),
            ("Invoice Date", fmt_date(spec.invoice_date, st)),
            ("Due Date", fmt_date(spec.due_date, st)),
            ("PO Number", spec.po_number or "-"),
        ]
        y = h - 85
        for k, v in meta:
            c.drawRightString(w - 130, y, f"{k}:")
            c.drawRightString(w - 40, y, v)
            y -= 13

    if spec.banner:
        c.setFillColor(HexColor("#b91c1c"))
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(w / 2, h - 150, spec.banner)

    # Bill to
    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, h - 175, "Rechnungsempfänger / Bill To" if st == "eu" else "Bill To")
    c.setFont("Helvetica", 9)
    y = h - 188
    for line in BILL_TO:
        c.drawString(40, y, line)
        y -= 12

    # Line items
    top = h - 260
    cols = [40, 330, 400, 490] if st == "us" else [40, 320, 395, 485]
    c.setFillColor(HexColor("#f3f4f6"))
    c.rect(36, top - 4, w - 72, 18, stroke=0, fill=1)
    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 9)
    heads = ["Description", "Qty", "Unit Price", "Amount"] if st == "us" else ["Beschreibung / Description", "Menge", "Einzelpreis", "Betrag"]
    c.drawString(cols[0], top + 2, heads[0])
    c.drawRightString(cols[1] + 30, top + 2, heads[1])
    c.drawRightString(cols[2] + 50, top + 2, heads[2])
    c.drawRightString(w - 40, top + 2, heads[3])
    c.setFont("Helvetica", 9)
    y = top - 18
    for ln in spec.lines:
        c.drawString(cols[0], y, ln.description)
        c.drawRightString(cols[1] + 30, y, fmt_qty(ln.qty, st))
        c.drawRightString(cols[2] + 50, y, fmt(ln.unit_price, st))
        c.drawRightString(w - 40, y, fmt(ln.amount, st))
        y -= 16

    # Totals
    y -= 10
    c.line(330, y + 8, w - 40, y + 8)
    rate_pct = (spec.tax_rate * 100).normalize()
    totals = [
        ("Subtotal" if st == "us" else "Zwischensumme / Subtotal", fmt(spec.subtotal, st)),
        (f"{spec.tax_label} ({fmt_qty(rate_pct, st)}%)", fmt(spec.tax, st)),
        (f"Total {spec.currency}" if st == "us" else f"Gesamt / Total {spec.currency}", fmt(spec.total, st)),
    ]
    for i, (k, v) in enumerate(totals):
        c.setFont("Helvetica-Bold" if i == 2 else "Helvetica", 10 if i == 2 else 9)
        c.drawRightString(w - 130, y - 4, k)
        c.drawRightString(w - 40, y - 4, v)
        y -= 15

    # Payment details
    y -= 25
    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, y, "Bankverbindung / Payment details" if st == "eu" else "Payment details")
    c.setFont("Helvetica", 9)
    y -= 13
    b = spec.bank
    pay = [f"Account name: {b.get('account_name', spec.vendor_name)}"]
    if b.get("iban"):
        pay.append(f"IBAN: {_group(b['iban'])}")
    if b.get("swift"):
        pay.append(f"SWIFT/BIC: {b['swift']}")
    if b.get("account_number"):
        pay.append(f"Account number: {b['account_number']}")
    if b.get("routing"):
        pay.append(f"Routing (ABA): {b['routing']}")
    for line in pay:
        c.drawString(40, y, line)
        y -= 12

    # Notes
    if spec.notes:
        y -= 10
        c.setFillColor(muted)
        for line in spec.notes:
            c.drawString(40, y, line)
            y -= 12
        c.setFillColor(ink)

    # Button with a link annotation
    if spec.button:
        label, url = spec.button
        y -= 30
        c.setFillColor(accent)
        c.roundRect(40, y, 170, 24, 4, stroke=0, fill=1)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(125, y + 8, label)
        c.linkURL(url, (40, y, 210, y + 24), relative=0)
        c.setFillColor(ink)

    # Footer
    c.setFont("Helvetica", 7)
    c.setFillColor(muted)
    c.drawCentredString(w / 2, 30, f"{spec.vendor_name} · Thank you for your business.")

    # Hidden text: invisible (or nearly) to a human reader, but extracted by any
    # PDF text parser (and therefore seen by an AI agent).
    #   white   - white, 1pt, at the bottom margin (the golden-path default)
    #   tiny    - normal ink but 1pt: a speck, not white
    #   offpage - normal size, drawn left of the page box
    if spec.hidden_text:
        if spec.hidden_style == "offpage":
            c.setFillColor(ink)
            c.setFont("Helvetica", 8)
            hx, hy, step = -2000, 200, 10
        else:
            c.setFillColor(white if spec.hidden_style == "white" else ink)
            c.setFont("Helvetica", 1)
            hx, hy, step = 40, 20, 2
        for line in spec.hidden_text:
            c.drawString(hx, hy, line)
            hy -= step

    c.showPage()
    c.save()


def _group(iban: str) -> str:
    s = iban.replace(" ", "")
    return " ".join(s[i:i + 4] for i in range(0, len(s), 4))
