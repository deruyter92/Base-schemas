"""Validation for lab-facing pseudonymous codes (``subject_code``, ``session_code``)."""

from __future__ import annotations

import re

_CODE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def normalize_code(value: str, *, field: str, max_length: int) -> str:
    """Strip ``value`` and check it is a pseudonymous code.

    Codes are shared with the consortium, so they must never contain a real
    name, initials, a birth date or other identifying information. The format
    check (ASCII letters, digits, ``.``, ``_``, ``-``; no spaces) rejects
    free-text names such as ``"Jan de Vries"``; it cannot catch every
    identifying code, so choosing a pseudonym remains the lab's duty.

    Args:
        value: Raw code, e.g. ``" P012 "``.
        field: Field name used in error messages, e.g. ``"subject_code"``.
        max_length: Maximum length (the column width).

    Returns:
        The stripped code.

    Raises:
        ValueError: If the code is empty, too long, or not in the allowed format.
    """
    code = value.strip()
    if not code:
        raise ValueError(f"{field} must be a non-empty string")
    if len(code) > max_length:
        raise ValueError(f"{field} {code!r} is longer than {max_length} characters")
    if not _CODE_RE.fullmatch(code):
        raise ValueError(
            f"{field} {code!r} must be a pseudonymous code of ASCII letters, digits, "
            "'.', '_' or '-' (no spaces; never a real name)"
        )
    return code
