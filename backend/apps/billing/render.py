"""Helpers for the printable invoice."""
from decimal import Decimal
from io import BytesIO
from urllib.parse import quote

ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
        "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _below_thousand(n: int) -> str:
    words = []
    if n >= 100:
        words.append(ONES[n // 100] + " Hundred")
        n %= 100
    if n >= 20:
        words.append(TENS[n // 10] + (" " + ONES[n % 10] if n % 10 else ""))
    elif n > 0:
        words.append(ONES[n])
    return " ".join(words)


def amount_in_words(amount) -> str:
    """Indian numbering: 'Rupees One Lakh Twenty Three Thousand ... and Fifty Paise Only'."""
    amount = Decimal(amount).quantize(Decimal("0.01"))
    rupees, paise = int(amount), int((amount - int(amount)) * 100)
    if rupees == 0 and paise == 0:
        return "Rupees Zero Only"
    parts = []
    for value, name in ((10_000_000, "Crore"), (100_000, "Lakh"), (1000, "Thousand")):
        if rupees >= value:
            parts.append(_below_thousand(rupees // value) + " " + name)
            rupees %= value
    if rupees:
        parts.append(_below_thousand(rupees))
    text = "Rupees " + " ".join(parts) if parts else "Rupees Zero"
    if paise:
        text += f" and {_below_thousand(paise)} Paise"
    return text + " Only"


def upi_qr_svg(upi_id: str, name: str, amount, note: str):
    """Inline SVG of a UPI payment QR (works with any UPI app). Returns '' when no UPI id is configured."""
    if not upi_id:
        return ""
    import segno

    uri = f"upi://pay?pa={quote(upi_id)}&pn={quote(name)}&am={Decimal(amount):.2f}&cu=INR&tn={quote(note)}"
    buf = BytesIO()
    segno.make(uri, error="m").save(buf, kind="svg", scale=3, border=1, xmldecl=False, svgns=True, nl=False)
    return buf.getvalue().decode()


def hsn_summary(lines):
    """HSN-wise taxable value and tax, as required on GST invoices."""
    rows = {}
    for l in lines:
        key = (l.hsn_code or l.package.product.hsn_code, l.tax_rate)
        r = rows.setdefault(key, {"hsn": key[0], "rate": key[1], "taxable": Decimal("0"), "tax": Decimal("0")})
        r["taxable"] += l.taxable_amount
        r["tax"] += l.tax_amount
    return list(rows.values())
