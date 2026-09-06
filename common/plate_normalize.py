"""Plate string cleanup + validation. Shared by M2 (OCR) and M3 (ingestion)."""
import re

# Indian format: SS RR L(LL) NNNN  e.g. MH 12 AB 1234
PLATE_RE = re.compile(r"^[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{1,4}$")

# Common OCR character confusions (used only where a digit is expected).
DIGIT_FIXES = {"O": "0", "I": "1", "Q": "0", "Z": "2", "S": "5", "B": "8", "D": "0"}
ALPHA_FIXES = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z"}


def _strip(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", raw or "").upper()


def is_valid(plate: str) -> bool:
    return bool(PLATE_RE.match(plate or ""))


def normalize_plate(raw: str) -> str | None:
    """Return a cleaned plate string, or None if too short to be a plate.

    Keeps imperfect strings (does not force a format match) so that
    multi-frame voting can still converge; validity is flagged separately
    via is_valid().
    """
    s = _strip(raw)
    if len(s) < 6:
        return None
    return s
