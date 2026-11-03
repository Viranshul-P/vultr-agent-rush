"""airlock_checks: helper library available inside the Airlock code sandbox.

Model-written programs import this to do reliable PDF parsing, money math,
bank-number validation, fuzzy matching and domain checks. The control plane
imports the pure-Python modules (money, bank, text, domains) to recompute
policy checks itself, so it never has to trust a sandbox's conclusions.

`pdf` and `scan` need pdfplumber and are only used inside the sandbox.
"""

from . import bank, domains, jsonio, money, text

io = jsonio  # documented name: airlock_checks.io.write_json

__all__ = ["bank", "domains", "io", "jsonio", "money", "text", "pdf", "scan"]


def __getattr__(name):  # lazy import of pdfplumber-dependent modules
    if name in ("pdf", "scan"):
        import importlib

        return importlib.import_module(f"{__name__}.{name}")
    raise AttributeError(name)
