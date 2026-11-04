from decimal import Decimal

import pytest
from airlock_checks import bank, domains, money, text


@pytest.mark.parametrize("raw,expected", [
    ("$4,830.00", "4830.00"), ("12.460,50", "12460.50"), ("€ 1 234,56", "1234.56"),
    ("1,234", "1234"), ("12,5", "12.5"), ("(99.00)", "-99.00"), ("1.234.567", "1234567"), ("9400", "9400"),
])
def test_money_parse(raw, expected):
    assert money.parse(raw) == Decimal(expected)


def test_money_parse_eu_hint():
    assert money.parse("1.234", locale_hint="eu") == Decimal("1234")
    assert money.parse("1.234") == Decimal("1.234")


@pytest.mark.parametrize("iban", ["GB82WEST12345698765432", "DE89 3704 0044 0532 0130 00",
                                  "FR1420041010050500013M02606", "GB33BUKB20201555555555"])
def test_iban_valid(iban):
    assert bank.iban(iban)["valid"]


def test_iban_invalid():
    assert not bank.iban("GB82WEST12345698765431")["valid"]
    assert not bank.iban("GB82WEST1234")["valid"]


def test_aba():
    assert bank.aba("011000015")
    assert not bank.aba("011000016")


def test_same_account():
    assert bank.same_account({"iban": "GB82 WEST 1234 5698 7654 32"}, {"iban": "GB82WEST12345698765432"})
    assert not bank.same_account({"iban": "GB33BUKB20201555555555"}, {"account_number": "000123456789", "routing": "011000015"})
    assert bank.same_account({"account_number": "000123456789", "routing": "011000015"},
                             {"account_number": "000123456789", "routing": "011000015"})


def test_domains():
    assert domains.of("Billing <billing@orchardcl0ud.example>") == "orchardcl0ud.example"
    assert domains.of("https://Filecourier-Secure.x.duckdns.org/v/1") == "filecourier-secure.x.duckdns.org"
    assert domains.lookalike("orchardcl0ud.example", ["orchardcloud.example"]) == 1.0
    assert domains.lookalike("brightline-billing.example", ["brightline-supply.example"]) >= 0.8
    assert domains.lookalike("orchardcloud.example", ["orchardcloud.example"]) == 0.0
    assert domains.lookalike("totally-unrelated.example", ["orchardcloud.example"]) < 0.8
    assert domains.host_matches("brightline.x.duckdns.org", ["brightline.x.duckdns.org"])
    assert not domains.host_matches("filecourier-secure.x.duckdns.org", ["brightline.x.duckdns.org"])


def test_fuzzy():
    assert text.fuzzy("Brightline Office Supply Ltd", "Brightline Office Supply") > 0.8
    assert text.ratio("INV-2026-0397-R", "INV-2026-0397") >= 0.9
    assert text.ratio("INV-2026-0412", "INV-2026-0397") < 0.9


def test_extraction_helpers_on_two_column_layouts():
    from airlock_checks import text as T

    doc = ("London E14 9AB, United Kingdom Invoice Number: INV-2026-0412\n"
           "ap@x.example Invoice Date: 2026-10-28\nDatum / Date: 27.10.2026 rechnung@k.example\n"
           "Account name: Brightline Office Supply Ltd\nTotal USD 4,643.93\n")
    assert T.after(doc, ["Invoice No.", "Invoice Number"], token=True) == "INV-2026-0412"
    assert T.iso_date(T.after(doc, "Invoice Date", token=True)) == "2026-10-28"
    assert T.iso_date(T.after(doc, "Date", token=True)) in ("2026-10-28", "2026-10-27")
    assert T.iso_date("27.10.2026") == "2026-10-27"
    assert T.after(doc, "Account name") == "Brightline Office Supply Ltd"
    assert T.find(doc, r"Total\s+([A-Z]{3})") == "USD"
    assert T.find(doc, r"Brightline Office Supply Ltd") == "Brightline Office Supply Ltd"  # no group: no IndexError
    assert T.find(doc, r"nope (\d+)", default="-") == "-"
    assert T.after(doc, "Missing label") is None


def test_after_skips_bilingual_label_pair():
    """'Rechnungsnr. / Invoice No.: X': matching the German label must not return '/'.
    Seen live: golden invoice #2 extracted invoice_number='/' and po_number='/' -> held by R8."""
    from airlock_checks import text as T

    doc = ("Rechnungsnr. / Invoice No.: EV-2026-1021\nDatum / Date: 22.10.2026\n"
           "Bestellnr. / PO: PO-2077\nFällig / Due: 21.11.2026\n")
    assert T.after(doc, "Rechnungsnr.", token=True) == "EV-2026-1021"
    assert T.after(doc, ["Bestellnr.", "PO"], token=True) == "PO-2077"
    assert T.iso_date(T.after(doc, "Datum", token=True)) == "2026-10-22"
    assert T.after(doc, "Bestellnr.") == "PO-2077"
    # the English half still works, and ordinary values containing '/' are untouched
    assert T.after(doc, "Invoice No.", token=True) == "EV-2026-1021"
    assert T.after("Ref: A/B 12\n", "Ref") == "A/B 12"
    assert T.after("Route: / \n", "Route") is None  # a bare separator is not a value


def test_money_extraction_helpers():
    from decimal import Decimal as D

    from airlock_checks import money as M

    doc = ("Description Qty Unit Price Amount\n"
           "Freight Rotterdam - Hamburg, full truck load 4 2.350,00 9.400,00\n"
           "Customs clearance 4 185,00 740,00\n"
           "IBAN: DE89 3704 0044 0532 0130 00\n"
           "Zwischensumme / Subtotal 10.140,00\nMwSt. / VAT (19%) 1.926,60\nGesamt / Total EUR 12.066,60\n")
    rows = M.line_items(doc, "eu")
    assert [r["amount"] for r in rows] == [D("9400.00"), D("740.00")]  # IBAN line rejected by arithmetic
    assert M.amount_after(doc, "Subtotal", "eu") == D("10140.00")
    assert M.amount_after(doc, "VAT", "eu") == D("1926.60")            # not 191926.60
    assert M.amount_after(doc, "Total", "eu") == D("12066.60")         # not the Subtotal line
    assert M.amount_after(doc, "Shipping", "eu", default=0) == 0


def test_find_iban_keeps_short_last_group_and_never_hides_bad_ibans():
    from airlock_checks import bank as B

    assert B.find_iban("IBAN: DE89 3704 0044 0532 0130 00\nSWIFT/BIC: COBADEFFXXX") == "DE89370400440532013000"
    assert B.find_iban("IBAN: GB82 WEST 1234 5698 7654 32") == "GB82WEST12345698765432"
    bad = B.find_iban("IBAN: DE89 3704 0044 0532 0130 01")
    assert bad and not B.iban(bad)["valid"]   # returned (so policy R6 blocks it), not silently dropped
    assert B.find_iban("no bank details") is None
