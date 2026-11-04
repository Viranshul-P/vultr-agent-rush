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
