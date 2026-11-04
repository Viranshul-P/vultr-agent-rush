"""Typed contracts between sandbox output, LLMs, policy and UI.

Everything that comes out of a sandbox or an LLM is validated against these
models before the control plane uses it. Invalid output = failed attempt.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Str40 = Annotated[str, Field(max_length=40)]
Str120 = Annotated[str, Field(max_length=120)]
Str200 = Annotated[str, Field(max_length=200)]
Str300 = Annotated[str, Field(max_length=300)]


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class Line(_Base):
    description: Str200
    qty: Decimal = Field(ge=0, le=Decimal("1e9"))
    unit_price: Decimal = Field(ge=0, le=Decimal("1e12"))
    amount: Decimal = Field(ge=Decimal("-1e12"), le=Decimal("1e12"))


class Bank(_Base):
    iban: Annotated[str, Field(max_length=40)] | None = None
    account_number: Annotated[str, Field(max_length=34)] | None = None
    routing: Annotated[str, Field(max_length=12)] | None = None
    swift: Annotated[str, Field(max_length=11)] | None = None
    account_name: Str120 | None = None

    @field_validator("iban")
    @classmethod
    def _norm_iban(cls, v):
        return v.replace(" ", "").upper() if v else v


class InvoiceFields(_Base):
    vendor_name: Str120
    sender_email: Annotated[str, Field(max_length=200)] | None = None
    invoice_number: Str40
    invoice_date: dt.date
    due_date: dt.date | None = None
    po_number: Str40 | None = None
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    lines: Annotated[list[Line], Field(max_length=100)]
    subtotal: Decimal
    tax: Decimal = Decimal("0")
    total: Decimal
    bank: Bank = Field(default_factory=Bank)
    links: Annotated[list[Annotated[str, Field(max_length=2000)]], Field(max_length=10)] = []
    notes: Annotated[str, Field(max_length=500)] = ""

    @field_validator("currency", mode="before")
    @classmethod
    def _upper_currency(cls, v):
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator("tax", mode="before")
    @classmethod
    def _tax_default(cls, v):
        return Decimal("0") if v is None else v

    @field_validator("notes", mode="before")
    @classmethod
    def _notes_default(cls, v):
        return "" if v is None else v

    @field_validator("links", mode="before")
    @classmethod
    def _links_default(cls, v):
        return [] if v is None else v

    @field_validator("links")
    @classmethod
    def _http_only(cls, v):
        return [u for u in v if u.lower().startswith(("http://", "https://"))]


CheckId = Literal["arith", "iban_valid", "bank_matches_master", "sender_domain", "duplicate",
                  "po_exists", "three_way_qty", "three_way_price", "vendor_known"]


class Check(_Base):
    id: CheckId
    passed: bool
    detail: Str300 = ""


class ChecksResult(_Base):
    checks: list[Check]


class ScanResult(_Base):
    ok: bool
    error: str | None = None
    text: str = ""
    text_truncated: bool = False
    hidden_text: list[Str300] = []
    links: list[Annotated[str, Field(max_length=2000)]] = []
    metadata: dict[str, str] = {}
    size_bytes: int = 0


class DetectorReport(_Base):
    hidden_text: list[Str300] = []
    keyword_hits: list[Str120] = []
    safety_flag: bool | None = None
    classifier_score: float | None = None
    classifier_quotes: list[Str300] = []
    static_flags: list[str] = []
    injection_suspected: bool = False
    reasons: list[Str200] = []


class BrowserVerdict(_Base):
    url: str
    final_url: str = ""
    credential_harvest: bool = False
    brand_claimed: Str120 | None = None
    domain_matches_vendor: bool = False
    downloads_seen: int = 0
    confidence: float = Field(default=0.0, ge=0, le=1)
    reasons: list[Str200] = []
    source: Literal["vision", "rules", "vision+rules", "unavailable"] = "rules"
    run_id: str | None = None


class RuleHit(_Base):
    id: str
    outcome: Literal["QUARANTINE", "BLOCK", "HOLD"]
    message: Str200
    detail: Str300 = ""


Outcome = Literal["CLEAR", "HOLD", "BLOCK", "QUARANTINE"]


class PolicyResult(_Base):
    outcome: Outcome
    rules_fired: list[RuleHit] = []
    checks: list[Check] = []
    vendor_id: str | None = None


class Summary(_Base):
    headline: Str120
    reasons: Annotated[list[Str200], Field(max_length=4)] = []
    recommended_action: Str200 = ""
