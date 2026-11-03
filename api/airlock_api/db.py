"""Database tables (SQLModel). SQLite for local dev, PostgreSQL in production."""

from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, Session, SQLModel, create_engine

from .config import settings


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def J(factory=None):  # JSON column helper: J(list), J(dict), or J() for nullable
    return Field(default_factory=factory or (lambda: None), sa_column=Column(JSON))


class Workspace(SQLModel, table=True):
    id: str = Field(primary_key=True)
    created_at: dt.datetime = Field(default_factory=utcnow)


class Vendor(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    aliases: list = J(list)
    email_domains: list = J(list)
    web_hosts: list = J(list)
    phone: str = ""
    currency: str = "USD"
    bank: dict = J(dict)


class PurchaseOrder(SQLModel, table=True):
    po_number: str = Field(primary_key=True)
    vendor_id: str
    currency: str
    status: str
    lines: list = J(list)


class Receipt(SQLModel, table=True):
    po_number: str = Field(primary_key=True)
    lines: list = J(list)


class ErpHistory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    vendor_id: str
    invoice_number: str
    po_number: str | None = None
    invoice_date: str
    paid_on: str
    currency: str
    total: str


class SeedInvoice(SQLModel, table=True):
    filename: str = Field(primary_key=True)
    order: int
    title: str
    expected: str
    file_key: str
    sha256: str


class Invoice(SQLModel, table=True):
    id: str = Field(primary_key=True, default_factory=lambda: new_id("inv"))
    workspace_id: str = Field(index=True)
    order: int = 0
    title: str = ""
    filename: str
    file_key: str
    sha256: str
    source: str = "seed"  # seed | upload
    expected: str | None = None  # golden-path label (seed only), shown in dev
    status: str = "NEW"
    fields: dict | None = J()
    detectors: dict | None = J()
    sandbox_checks: list | None = J()
    browser: list | None = J()
    policy: dict | None = J()
    summary: dict | None = J()
    blast_radius: dict | None = J()
    error: str | None = Field(default=None, sa_column=Column(Text))
    created_at: dt.datetime = Field(default_factory=utcnow)
    updated_at: dt.datetime = Field(default_factory=utcnow)


class Run(SQLModel, table=True):
    id: str = Field(primary_key=True)
    invoice_id: str | None = Field(default=None, index=True)
    kind: str
    attempt: int = 1
    tier: str = ""
    container_id: str = ""
    image_digest: str = ""
    code: str | None = Field(default=None, sa_column=Column(Text))
    static_flags: list = J(list)
    limits: dict = J(dict)
    isolation: dict = J(dict)
    exit_code: int | None = None
    killed_reason: str | None = None
    stdout: str | None = Field(default=None, sa_column=Column(Text))
    stderr: str | None = Field(default=None, sa_column=Column(Text))
    artifacts: list = J(list)  # [{name, sha256, size, key}]
    extra: dict = J(dict)
    created_at: str | None = None
    started_at: str | None = None
    destroyed_at: str | None = None
    duration_ms: int = 0
    peak_mem_mb: float | None = None


class Event(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    invoice_id: str = Field(index=True)
    ts: dt.datetime = Field(default_factory=utcnow)
    type: str
    payload: dict = J(dict)


class Approval(SQLModel, table=True):
    id: str = Field(primary_key=True, default_factory=lambda: new_id("apr"))
    invoice_id: str = Field(index=True)
    decision: str
    note: str = ""
    ts: dt.datetime = Field(default_factory=utcnow)


class ErpPosting(SQLModel, table=True):
    id: str = Field(primary_key=True, default_factory=lambda: new_id("erp"))
    workspace_id: str = Field(index=True)
    invoice_id: str
    vendor_id: str | None
    invoice_number: str
    amount: str
    currency: str
    ts: dt.datetime = Field(default_factory=utcnow)


class Evidence(SQLModel, table=True):
    invoice_id: str = Field(primary_key=True)
    manifest_key: str
    manifest_sha256: str
    signature_b64: str
    sealed_at: dt.datetime = Field(default_factory=utcnow)


class LlmUsage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    invoice_id: str | None = Field(default=None, index=True)
    role: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    ok: bool = True
    ts: dt.datetime = Field(default_factory=utcnow, index=True)


class DrillResult(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    drill_id: str = Field(index=True)
    passed: bool | None = None
    actual: str = Field(default="", sa_column=Column(Text))
    tier: str = ""
    data: dict = J(dict)
    ts: dt.datetime = Field(default_factory=utcnow)


_url = settings.database_url
if _url.startswith("sqlite:///"):
    Path(_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(_url, connect_args={"check_same_thread": False} if _url.startswith("sqlite") else {},
                       pool_pre_ping=not _url.startswith("sqlite"))


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def session() -> Session:
    return Session(engine, expire_on_commit=False)


def to_dict(obj: Any) -> dict:
    d = obj.model_dump()
    for k, v in d.items():
        if isinstance(v, dt.datetime):
            d[k] = v.isoformat()
    return d
