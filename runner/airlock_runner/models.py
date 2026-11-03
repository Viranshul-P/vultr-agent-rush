from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_RUN_ID = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
_FILE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


class Limits(BaseModel):
    timeout_s: int = Field(30, ge=1, le=120)
    memory_mb: int = Field(512, ge=64, le=2048)
    cpus: float = Field(1.0, gt=0, le=2)
    pids: int = Field(128, ge=16, le=512)
    out_max_mb: int = Field(10, ge=1, le=50)


class InFile(BaseModel):
    name: str
    b64: str

    @field_validator("name")
    @classmethod
    def _safe_name(cls, v):
        if not _FILE.match(v) or v in (".", ".."):
            raise ValueError("bad file name")
        return v


class ExecRequest(BaseModel):
    run_id: str
    kind: Literal["scan", "extract", "validate", "drill", "probe"] = "extract"
    code: str = Field(max_length=200_000)
    files: list[InFile] = Field(default_factory=list, max_length=10)
    limits: Limits = Field(default_factory=Limits)

    @field_validator("run_id")
    @classmethod
    def _safe_id(cls, v):
        if not _RUN_ID.match(v):
            raise ValueError("bad run_id")
        return v


class BrowseRequest(BaseModel):
    run_id: str
    url: str = Field(max_length=2000)
    timeout_s: int = Field(45, ge=5, le=90)
    limits: Limits = Field(default_factory=lambda: Limits(memory_mb=1024, pids=256, timeout_s=60))

    @field_validator("run_id")
    @classmethod
    def _safe_id(cls, v):
        if not _RUN_ID.match(v):
            raise ValueError("bad run_id")
        return v

    @field_validator("url")
    @classmethod
    def _http(cls, v):
        if not v.lower().startswith(("http://", "https://")):
            raise ValueError("only http(s) URLs")
        return v


class Artifact(BaseModel):
    name: str
    b64: str | None = None  # omitted for quarantined files
    sha256: str
    size: int


class RunResult(BaseModel):
    run_id: str
    kind: str
    container_id: str
    image_digest: str
    tier: str
    exit_code: int | None
    killed_reason: Literal["timeout", "oom", "pids", "output_cap", "error"] | None = None
    stdout: str = ""
    stderr: str = ""
    artifacts: list[Artifact] = []
    created_at: str
    started_at: str | None = None
    destroyed_at: str | None = None
    duration_ms: int = 0
    peak_mem_mb: float | None = None
    isolation: dict = {}
    limits: dict = {}
    extra: dict = {}  # browse: screenshots meta, proxy_log, downloads, etc.
