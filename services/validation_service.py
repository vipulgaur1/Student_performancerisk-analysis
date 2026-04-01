"""
services/validation_service.py
--------------------------------
Validates and sanitises student feature data before it reaches the ML model.

Rules applied per field:
  - Type coercion: anything that cannot be cast to float/int is replaced by
    the field's configured default.
  - Range clamping: values outside the valid range are clipped to the boundary.
  - Missing-value fill: None / NaN / empty strings are replaced by defaults.
  - Categorical check: values not in the allowed set are replaced by defaults.

All rules are table-driven so new fields can be added without touching logic.
"""

import logging
import math

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field specification table
# ---------------------------------------------------------------------------
FIELD_SPEC = {
    # ---- Continuous 0–100 ------------------------------------------------
    "attendance": {
        "type": "float", "min": 0.0, "max": 100.0, "default": 75.0, "allowed": None
    },
    "mid_term_marks": {
        "type": "float", "min": 0.0, "max": 100.0, "default": 50.0, "allowed": None
    },
    "class_test_score": {
        "type": "float", "min": 0.0, "max": 100.0, "default": 50.0, "allowed": None
    },
    "quiz_avg_score": {
        "type": "float", "min": 0.0, "max": 100.0, "default": 50.0, "allowed": None
    },
    "assignment_completion": {
        "type": "float", "min": 0.0, "max": 100.0, "default": 75.0, "allowed": None
    },
    # ---- Numeric (non-negative, no hard upper cap) -----------------------
    "assignment_delay": {
        "type": "float", "min": 0.0, "max": None, "default": 0.0, "allowed": None
    },
    # ---- GPA (0–10) -------------------------------------------------------
    "previous_sem_gpa": {
        "type": "float", "min": 0.0, "max": 10.0, "default": 5.0, "allowed": None
    },
    # ---- Numeric (non-negative integer) -----------------------------------
    "backlogs": {
        "type": "int", "min": 0, "max": None, "default": 0, "allowed": None
    },
    # ---- Categorical (0 = low, 1 = medium, 2 = high) --------------------
    "class_participation": {
        "type": "int", "min": 0, "max": 2, "default": 1, "allowed": {0, 1, 2}
    },
    "doubt_asking": {
        "type": "int", "min": 0, "max": 2, "default": 1, "allowed": {0, 1, 2}
    },
    "attention_level": {
        "type": "int", "min": 0, "max": 2, "default": 1, "allowed": {0, 1, 2}
    },
    "behaviour": {
        "type": "int", "min": 0, "max": 2, "default": 1, "allowed": {0, 1, 2}
    },
}

# Fields validated in declaration order
ALL_FIELDS = list(FIELD_SPEC.keys())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_missing(value) -> bool:
    """Return True for None, empty string, or any NaN-like float."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def _coerce(value, dtype: str):
    """
    Try to cast value to dtype ('float' or 'int').
    Returns (cast_value, success_bool).
    """
    try:
        if dtype == "int":
            return int(float(value)), True   # accepts floats like 2.0 → 2
        else:
            return float(value), True
    except (TypeError, ValueError):
        return None, False


def _validate_field(field: str, raw_value):
    """
    Apply all validation rules to a single field.
    Returns (sanitised_value, list_of_warnings).
    """
    spec     = FIELD_SPEC[field]
    dtype    = spec["type"]
    default  = spec["default"]
    warnings = []

    # 1. Missing value
    if _is_missing(raw_value):
        warnings.append(f"'{field}' is missing — using default ({default})")
        return default, warnings

    # 2. Type coercion
    value, ok = _coerce(raw_value, dtype)
    if not ok:
        warnings.append(
            f"'{field}' has invalid type (got {repr(raw_value)}) — using default ({default})"
        )
        return default, warnings

    # 3. Categorical check (before range clamping so the message is clear)
    if spec["allowed"] is not None:
        if value not in spec["allowed"]:
            warnings.append(
                f"'{field}' value {value} not in allowed set {spec['allowed']} "
                f"— using default ({default})"
            )
            return default, warnings

    # 4. Range clamping
    lo, hi   = spec["min"], spec["max"]
    clamped  = value
    if lo is not None and value < lo:
        clamped = lo
        warnings.append(f"'{field}' value {value} below minimum {lo} — clamped to {lo}")
    if hi is not None and value > hi:
        clamped = hi
        warnings.append(f"'{field}' value {value} above maximum {hi} — clamped to {hi}")

    # 5. Final type enforcement after clamping
    if dtype == "int":
        clamped = int(clamped)

    return clamped, warnings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ValidationResult:
    """
    Carries the outcome of a validate_student_data() call.

    Attributes
    ----------
    cleaned  : dict  — sanitised feature values ready for the model
    warnings : list  — human-readable corrections made (non-fatal)
    errors   : list  — fatal errors (reserved for future hard-reject logic)
    is_valid : bool  — True when errors list is empty
    """
    __slots__ = ("cleaned", "warnings", "errors", "is_valid")

    def __init__(self, cleaned: dict, warnings: list, errors: list):
        self.cleaned  = cleaned
        self.warnings = warnings
        self.errors   = errors
        self.is_valid = len(errors) == 0


def validate_student_data(raw_data: dict) -> ValidationResult:
    """
    Validate and sanitise a student data dictionary.

    Parameters
    ----------
    raw_data : dict
        Raw input from CSV row, JSON payload, or DB row.
        Extra keys are ignored; missing keys are filled with defaults.

    Returns
    -------
    ValidationResult
        .cleaned   — dict with all FIELD_SPEC keys, sanitised
        .warnings  — list of non-fatal correction messages
        .is_valid  — True (warnings are non-fatal)
    """
    cleaned      = {}
    all_warnings = []
    all_errors   = []

    for field in ALL_FIELDS:
        raw_value          = raw_data.get(field)
        sanitised, warns   = _validate_field(field, raw_value)
        cleaned[field]     = sanitised
        all_warnings.extend(warns)

    if all_warnings:
        logger.warning(
            "Validation corrections for student '%s':\n  %s",
            raw_data.get("student_id", "<unknown>"),
            "\n  ".join(all_warnings),
        )

    return ValidationResult(cleaned=cleaned, warnings=all_warnings, errors=all_errors)


def validate_batch(rows: list) -> list:
    """Validate a list of raw student dicts. Returns ValidationResult per row."""
    return [validate_student_data(row) for row in rows]