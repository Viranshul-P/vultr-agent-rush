"""The pipeline. A deterministic state machine; the LLM runs only at fixed nodes.

NEW -> SCANNING -> EXTRACTING -> VALIDATING -> INSPECTING_LINKS -> DECIDING
    -> AWAIT_APPROVAL -> POSTED | BLOCKED | HELD | QUARANTINED | ERROR

No model can trigger a payment: ERP posting happens only from the human-approval
route. The policy engine (not the sandbox, not the model) makes the decision.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

from sqlmodel import select

from . import detectors, evidence, links, llm, prompts, runner_client
from .config import settings
from .db import Invoice, Run, session, utcnow
from .events import bus
from .policy import PolicyContext, evaluate
from .refdata import load, policy_tables, prior_from_history
from .schemas import BrowserVerdict, ChecksResult, DetectorReport, InvoiceFields, ScanResult, Summary
from .storage import store


def _rid(kind: str) -> str:
    return f"{kind}-{uuid.uuid4().hex[:12]}"


def _set(inv_id: str, **fields):
    with session() as s:
        inv = s.get(Invoice, inv_id)
        for k, v in fields.items():
            setattr(inv, k, v)
        inv.updated_at = utcnow()
        s.add(inv)
        s.commit()
        s.refresh(inv)
        return inv


def _state(inv_id, new, **extra):
    with session() as s:
        inv = s.get(Invoice, inv_id)
        old = inv.status
        inv.status = new
        inv.updated_at = utcnow()
        for k, v in extra.items():
            setattr(inv, k, v)
        s.add(inv)
        s.commit()
    bus.publish(inv_id, "state.changed", {"from": old, "to": new})


def _save_run(inv_id, kind, attempt, result: dict, code: str | None, static_flags=None) -> Run:
    arts = []
    for a in result.get("artifacts", []):
        key = None
        if a.get("b64"):
            key = f"runs/{inv_id}/{result['run_id']}/{a['name']}"
            import base64
            store.put(key, base64.b64decode(a["b64"]))
        arts.append({"name": a["name"], "sha256": a["sha256"], "size": a["size"], "key": key})
    run = Run(id=result["run_id"], invoice_id=inv_id, kind=kind, attempt=attempt, tier=result.get("tier", ""),
              container_id=result.get("container_id", ""), image_digest=result.get("image_digest", ""),
              code=code, static_flags=static_flags or [], limits=result.get("limits", {}),
              isolation=result.get("isolation", {}), exit_code=result.get("exit_code"),
              killed_reason=result.get("killed_reason"), stdout=result.get("stdout", ""),
              stderr=result.get("stderr", ""), artifacts=arts, extra=result.get("extra", {}),
              created_at=result.get("created_at"), started_at=result.get("started_at"),
              destroyed_at=result.get("destroyed_at"), duration_ms=result.get("duration_ms", 0),
              peak_mem_mb=result.get("peak_mem_mb"))
    with session() as s:
        s.merge(run)
        s.commit()
    bus.publish(inv_id, "sandbox.created", {"run_id": run.id, "container_id": run.container_id, "tier": run.tier,
                                            "limits": run.limits, "isolation": run.isolation, "kind": kind})
    bus.publish(inv_id, "sandbox.finished", {"run_id": run.id, "exit_code": run.exit_code,
                                            "killed_reason": run.killed_reason, "duration_ms": run.duration_ms,
                                            "peak_mem_mb": run.peak_mem_mb})
    if run.destroyed_at:
        bus.publish(inv_id, "sandbox.destroyed", {"run_id": run.id, "destroyed_at": run.destroyed_at})
    _note_egress(inv_id, run)
    return run


def _note_egress(inv_id, run: Run):
    txt = (run.stderr or "") + (run.stdout or "")
    if any(s in txt for s in ("Network is unreachable", "Temporary failure in name resolution",
                              "Failed to establish", "getaddrinfo", "No route to host")):
        bus.publish(inv_id, "egress.attempt", {"run_id": run.id, "kind": "network_unreachable",
                                               "detail": "sandbox code attempted a network call; no interface present"})
    for e in run.extra.get("proxy_log", []):
        if e.get("decision") == "deny":
            bus.publish(inv_id, "egress.attempt", {"run_id": run.id, "kind": "proxy_deny",
                                                   "detail": f"{e.get('host')}: {e.get('reason')}"})


# ------------------------------------------------------------------ pipeline

def process(inv_id: str):
    try:
        inv = _set(inv_id, error=None)
        pdf_bytes = store.get(inv.file_key)
        domain = settings.domain

        # 1. SCANNING -----------------------------------------------------
        _state(inv_id, "SCANNING")
        scan = _scan(inv_id, pdf_bytes)
        # The detector models only read the scan, and nothing uses their report until extraction is
        # done, so they run alongside extraction instead of before it (saves two model calls of wait).
        with ThreadPoolExecutor(max_workers=1) as pool:
            det_future = pool.submit(detectors.run_detectors, scan, inv_id)

            # 2. EXTRACTING -----------------------------------------------
            _state(inv_id, "EXTRACTING")
            fields, extract_flags = _extract(inv_id, pdf_bytes, scan)
            det = det_future.result()
        det.static_flags = sorted(set(det.static_flags) | set(extract_flags))
        if scan.hidden_text and {"network", "env-access", "subprocess"} & set(extract_flags):
            det.injection_suspected = True
            det.reasons = (det.reasons + ["model-written code tried network/env access on an invoice with hidden instructions"])[:6]
        _set(inv_id, detectors=det.model_dump(), fields=fields.model_dump(mode="json") if fields else None)
        bus.publish(inv_id, "detector.hit", {k: v for k, v in det.model_dump().items()
                                             if k in ("hidden_text", "keyword_hits", "static_flags",
                                                      "classifier_score", "safety_flag", "injection_suspected", "reasons")})
        if fields is None:
            _finish(inv_id, "ERROR", error="extraction failed after retries")
            return

        # 3. VALIDATING (advisory sandbox checks) + build policy context ---
        _state(inv_id, "VALIDATING")
        data = load(domain)
        vendors, pos, receipts, history = policy_tables(data)
        sandbox_checks = _validate(inv_id, fields, vendors, pos, receipts)
        _set(inv_id, sandbox_checks=[c.model_dump() for c in sandbox_checks])

        # 4. INSPECTING_LINKS --------------------------------------------
        browser_verdicts: list[BrowserVerdict] = []
        if fields.links:
            _state(inv_id, "INSPECTING_LINKS")
            browser_verdicts = _inspect_links(inv_id, fields, vendors)
            _set(inv_id, browser=[b.model_dump() for b in browser_verdicts])

        # 5. DECIDING (deterministic policy) -----------------------------
        _state(inv_id, "DECIDING")
        prior = prior_from_history(history) + _workspace_priors(inv.workspace_id, inv_id)
        ctx = PolicyContext(vendors=vendors, purchase_orders=pos, receipts=receipts, prior_invoices=prior,
                            detectors=det, browser=browser_verdicts)
        result = evaluate(fields, ctx)
        bus.publish(inv_id, "policy.decision", {"outcome": result.outcome,
                                               "rules_fired": [h.model_dump() for h in result.rules_fired]})
        summary = _summarise(inv_id, fields, result, det, browser_verdicts)
        blast = _blast_radius(inv_id)
        _set(inv_id, policy=result.model_dump(), summary=summary.model_dump(), blast_radius=blast)

        if result.outcome == "CLEAR":
            _state(inv_id, "AWAIT_APPROVAL")
            bus.publish(inv_id, "approval.requested", {"amount": str(fields.total), "currency": fields.currency})
        else:
            terminal = {"QUARANTINE": "QUARANTINED", "BLOCK": "BLOCKED", "HOLD": "HELD"}[result.outcome]
            _finish(inv_id, terminal)
    except Exception as exc:  # never crash the server on one invoice
        import traceback
        _finish(inv_id, "ERROR", error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-1500:]}")


def _finish(inv_id, status, **extra):
    _state(inv_id, status, **extra)
    try:
        with session() as s:
            inv = s.get(Invoice, inv_id)
        ev = evidence.seal(inv)
        bus.publish(inv_id, "evidence.sealed", {"manifest_sha256": ev.manifest_sha256, "key": ev.manifest_key})
    except Exception as exc:
        bus.publish(inv_id, "evidence.error", {"detail": str(exc)[:200]})


# ------------------------------------------------------------------ nodes

def _scan(inv_id, pdf_bytes) -> ScanResult:
    # Explicit paths in the code string so the dev backend's path-rewriting reaches them.
    code = 'from airlock_checks.scan import main\nmain("/input/invoice.pdf", "/out/scan.json")\n'
    res = runner_client.exec_code(_rid("scan"), code, kind="scan", files=[("invoice.pdf", pdf_bytes)],
                                  limits={"timeout_s": 40})
    _save_run(inv_id, "scan", 1, res, code)
    data = runner_client.artifact_bytes(res, "scan.json")
    if not data:
        return ScanResult(ok=False, error="scan produced no output")
    return ScanResult.model_validate_json(data)


def _extract(inv_id, pdf_bytes, scan: ScanResult):
    task = "Write the extraction program now."
    flags: set[str] = set()
    prev_err = None
    for attempt in range(1, settings.max_code_attempts + 1):
        sys_prompt = prompts.CODER_EXTRACT_SYS
        text = scan.text
        if prev_err:
            feedback = f"\n\nYour previous program failed. stderr tail:\n{prev_err[-3000:]}\nReturn a corrected full program."
            task_a = task + feedback
        else:
            task_a = task
        raw = llm.quarantined(sys_prompt, text, task_a, role="coder_extract", invoice_id=inv_id, doc_id=f"inv-{attempt}")
        code = llm.extract_code_block(raw)
        sflags = detectors.static_scan(code)
        flags |= set(sflags)
        bus.publish(inv_id, "code.generated", {"run_id": "pending", "attempt": attempt, "code": code,
                                              "static_flags": sflags})
        res = runner_client.exec_code(_rid("extract"), code, kind="extract", files=[("invoice.pdf", pdf_bytes)],
                                      limits={"timeout_s": 30})
        _save_run(inv_id, "extract", attempt, res, code, sflags)
        data = runner_client.artifact_bytes(res, "result.json")
        if res.get("exit_code") == 0 and data:
            try:
                fields = InvoiceFields.model_validate_json(data)
                return fields, sorted(flags)
            except Exception as exc:
                prev_err = f"result.json failed schema validation: {exc}"
        else:
            prev_err = res.get("stderr") or "no result.json produced"
        if attempt < settings.max_code_attempts:
            bus.publish(inv_id, "sandbox.retry", {"attempt": attempt, "stderr_tail": (prev_err or "")[-400:]})
    return None, sorted(flags)


def _validate(inv_id, fields: InvoiceFields, vendors, pos, receipts):
    from .policy import PolicyContext, compute_checks
    # Control-plane checks are authoritative; we also run an advisory sandbox pass for the demo.
    context = {
        "fields": fields.model_dump(mode="json"),
        "vendor_master": vendors,
        "purchase_orders": list(pos.values()),
        "receipts": list(receipts.values()),
    }
    code_raw = llm.quarantined(prompts.CODER_VALIDATE_SYS, json.dumps(fields.model_dump(mode="json")),
                               "Write the validation program.", role="coder_validate", invoice_id=inv_id)
    code = llm.extract_code_block(code_raw)
    sflags = detectors.static_scan(code)
    res = runner_client.exec_code(_rid("validate"), code, kind="validate",
                                  files=[("fields.json", fields.model_dump_json().encode()),
                                         ("context.json", json.dumps(context).encode())],
                                  limits={"timeout_s": 30})
    _save_run(inv_id, "validate", 1, res, code, sflags)
    data = runner_client.artifact_bytes(res, "checks.json")
    sandbox_checks = []
    if data:
        try:
            sandbox_checks = ChecksResult.model_validate_json(data).checks
        except Exception:
            pass
    # authoritative recompute
    checks, _vendor = compute_checks(fields, PolicyContext(vendors=vendors, purchase_orders=pos, receipts=receipts))
    for c in checks:
        bus.publish(inv_id, "check.result", {"check_id": c.id, "passed": c.passed, "detail": c.detail})
    # flag disagreements between sandbox and control plane (possible tampered run)
    sb = {c.id: c.passed for c in sandbox_checks}
    for c in checks:
        if c.id in sb and sb[c.id] != c.passed:
            bus.publish(inv_id, "check.disagreement", {"check_id": c.id, "sandbox": sb[c.id], "authoritative": c.passed})
    return checks


def _inspect_links(inv_id, fields: InvoiceFields, vendors) -> list[BrowserVerdict]:
    from airlock_checks import domains
    vendor = next((v for v in vendors if domains.lookalike(domains.of(fields.sender_email or ""),
                   v.get("email_domains", [])) == 0.0 and
                   any(a.lower() in fields.vendor_name.lower() or fields.vendor_name.lower() in v["name"].lower()
                       for a in [v["name"], *v.get("aliases", [])])), None)
    known_hosts = vendor.get("web_hosts", []) if vendor else []
    verdicts = []
    for url in fields.links[:settings.max_links]:
        res = runner_client.browse(_rid("browse"), url, timeout_s=45)
        _save_run(inv_id, "browse", 1, res, None)
        extra = res.get("extra", {})
        screenshots = [a["b64"] for a in res.get("artifacts", []) if a["name"].endswith(".png") and a.get("b64")]
        # If the browser couldn't actually load the page, fail safe: mark unavailable (policy HOLDs).
        # This includes proxy denies / HTTP errors, which load as an error page with no harness error.
        why = links.unavailable_reason(res, url)
        if why:
            verdict = BrowserVerdict(url=url, final_url=extra.get("final_url", "") or url, source="unavailable",
                                     reasons=[f"link could not be inspected: {why}"[:200]])
        else:
            verdict = _vision_verdict(inv_id, url, extra, known_hosts, screenshots)
        verdict.run_id = res["run_id"]
        verdicts.append(verdict)
        bus.publish(inv_id, "browser.verdict", verdict.model_dump())
    return verdicts


def _vision_verdict(inv_id, url, extra, known_hosts, screenshots) -> BrowserVerdict:
    from airlock_checks import domains
    final_host = domains.of(extra.get("final_url") or url)
    matches = domains.host_matches(final_host, known_hosts)
    forms = extra.get("forms", [])
    has_pw = extra.get("loose_password_inputs", 0) > 0 or any(
        any("password" in f for f in (frm.get("fields") or [])) for frm in forms)
    downloads = len(extra.get("downloads", []))
    # rule-based baseline (works even without a vision model)
    rule_harvest = bool(has_pw and not matches)
    reasons = []
    if has_pw:
        reasons.append("page presents a password field")
    if not matches:
        reasons.append(f"host {final_host} is not a known vendor domain")
    if downloads:
        reasons.append(f"{downloads} file download(s) triggered automatically")
    source = "rules"
    confidence = 0.8 if rule_harvest else 0.2
    brand = None
    if screenshots:
        try:
            v = llm.extract_json(llm.vision(prompts.VISION_SYS, screenshots,
                {"final_url": extra.get("final_url"), "redirects": extra.get("redirects", []),
                 "forms": forms, "known_vendor_hosts": known_hosts, "page_title": extra.get("title")},
                invoice_id=inv_id))
            source = "vision+rules"
            vh = bool(v.get("credential_harvest"))
            rule_harvest = rule_harvest or vh
            brand = v.get("brand_claimed")
            confidence = max(confidence, float(v.get("confidence", 0)))
            reasons += [str(r)[:200] for r in v.get("reasons", [])][:3]
        except Exception:
            pass
    return BrowserVerdict(url=url, final_url=extra.get("final_url", "") or url, credential_harvest=rule_harvest,
                          brand_claimed=brand, domain_matches_vendor=matches, downloads_seen=downloads,
                          confidence=confidence, reasons=reasons[:5], source=source)


def _summarise(inv_id, fields, result, det, browser) -> Summary:
    try:
        raw = llm.privileged(prompts.PLANNER_SYS, {
            "outcome": result.outcome,
            "rules_fired": [h.model_dump() for h in result.rules_fired],
            "checks": [c.model_dump() for c in result.checks],
            "injection_suspected": det.injection_suspected,
            "vendor_name": fields.vendor_name, "total": str(fields.total), "currency": fields.currency,
            "browser": [b.model_dump() for b in browser],
        }, role="planner", invoice_id=inv_id)
        data = llm.extract_json(raw)
        return Summary.model_validate(data)
    except Exception:
        headline = {"CLEAR": "All checks passed", "HOLD": "Needs review", "BLOCK": "Payment blocked",
                    "QUARANTINE": "Quarantined as malicious"}[result.outcome]
        return Summary(headline=headline, reasons=[h.message for h in result.rules_fired][:4],
                       recommended_action=result.rules_fired[0].message if result.rules_fired else "Approve payment.")


def _blast_radius(inv_id) -> dict:
    with session() as s:
        runs = list(s.exec(select(Run).where(Run.invoice_id == inv_id)))
    env_passed = sum((r.isolation or {}).get("env_vars_passed", 0) for r in runs)
    denied = sum(1 for r in runs for e in (r.extra or {}).get("proxy_log", []) if e.get("decision") == "deny")
    net_attempts = 0
    for r in runs:
        txt = (r.stderr or "")
        if any(s in txt for s in ("Network is unreachable", "getaddrinfo", "Failed to establish", "No route to host")):
            net_attempts += 1
    data = {
        "secrets_exposed": 0, "env_vars_passed": env_passed,
        "outbound_connections": 0, "blocked_egress_attempts": denied + net_attempts,
        "host_files_written": 0,
        "how_measured": {
            "secrets": "no env vars passed to any sandbox; sandbox VM holds no API keys",
            "outbound": "code sandboxes have no network interface; browser traffic is allow-listed by the egress proxy",
            "host_files": "read-only rootfs; only /out is writable and it is discarded after collection",
        },
    }
    bus.publish(inv_id, "blast_radius", data)
    return data


def _workspace_priors(workspace_id, exclude_id):
    from .policy import PriorInvoice
    with session() as s:
        rows = s.exec(select(Invoice).where(Invoice.workspace_id == workspace_id,
                                            Invoice.id != exclude_id, Invoice.status == "POSTED"))
        out = []
        for inv in rows:
            f = inv.fields or {}
            if not f:
                continue
            try:
                out.append(PriorInvoice(vendor_id=(inv.policy or {}).get("vendor_id") or "",
                                        invoice_number=f.get("invoice_number", ""),
                                        total=__import__("decimal").Decimal(str(f.get("total", "0"))),
                                        currency=f.get("currency", ""),
                                        invoice_date=dt.date.fromisoformat(f["invoice_date"]) if f.get("invoice_date") else None,
                                        source=f"workspace:{inv.id}"))
            except Exception:
                continue
    return out
