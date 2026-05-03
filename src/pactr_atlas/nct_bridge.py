"""Extract NCT cross-references from ICTRP Secondary IDs.

Strict regex: ^NCT\\d{8}$ after stripping. Trials whose Secondary IDs
field carries no NCT are tagged tier0_invisible — a first-class equity
finding per spec, NOT a fuzzy-match fallback.
"""
from __future__ import annotations

import re
from typing import Optional

NCT_RE = re.compile(r"\bNCT(\d{8})\b")


def extract_nct(secondary_ids: Optional[str]) -> Optional[str]:
    if not secondary_ids:
        return None
    match = NCT_RE.search(secondary_ids)
    if not match:
        return None
    return f"NCT{match.group(1)}"


def is_tier0_invisible(nct: Optional[str]) -> bool:
    return not nct
