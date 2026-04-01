"""
services/prediction_service.py
--------------------------------
Loads the trained RandomForest model and exposes predict_category().

Flow
----
raw_data  →  alias normalisation
          →  validation_service.validate_student_data()
          →  _build_feature_vector()   (12 canonical features → model input)
          →  model.predict / predict_proba
          →  (prediction, confidence, recommended_action)

Feature set (12 canonical fields — must match train_model.py FEATURE_ORDER):
    attendance, mid_term_marks, class_test_score, quiz_avg_score,
    assignment_completion, assignment_delay, previous_sem_gpa, backlogs,
    class_participation, doubt_asking, attention_level, behaviour
"""

import joblib
import logging
import os
import numpy as np
import pandas as pd                          # added: needed for named-column DataFrame

from services.validation_service import validate_student_data

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------
MODEL_PATH = os.path.join(os.path.dirname(__file__), '../models/model.pkl')

try:
    _model = joblib.load(MODEL_PATH)
    logger.info("Model loaded successfully from %s", MODEL_PATH)
except Exception as _e:
    logger.error("Failed to load model: %s", _e)
    _model = None

# ---------------------------------------------------------------------------
# Canonical feature order — single source of truth shared with train_model.py
# ---------------------------------------------------------------------------
FEATURE_ORDER = [
    "attendance",            # 0–100
    "mid_term_marks",        # 0–100
    "class_test_score",      # 0–100
    "quiz_avg_score",        # 0–100
    "assignment_completion", # 0–100
    "assignment_delay",      # numeric ≥ 0
    "previous_sem_gpa",      # 0–10
    "backlogs",              # numeric ≥ 0
    "class_participation",   # 0, 1, 2
    "doubt_asking",          # 0, 1, 2
    "attention_level",       # 0, 1, 2
    "behaviour",             # 0, 1, 2
]

# ---------------------------------------------------------------------------
# Legacy column alias map — keeps old CSV uploads working transparently
# ---------------------------------------------------------------------------
_ALIAS_MAP = {
    "class_test":       "class_test_score",
    "assignment":       "assignment_completion",
    "assignment_score": "assignment_completion",
    "doubts":           "doubt_asking",
    "doubt_count":      "doubt_asking",
    "behavior":         "behaviour",
    "behavior_score":   "behaviour",
}


def _normalise_keys(raw: dict) -> dict:
    """Remap legacy field names to canonical names. Does not mutate caller's dict."""
    data = dict(raw)
    for old_key, new_key in _ALIAS_MAP.items():
        if old_key in data:
            if new_key not in data:
                data[new_key] = data.pop(old_key)
            else:
                data.pop(old_key)   # canonical already present; drop duplicate
    return data


def _build_feature_vector(cleaned: dict) -> pd.DataFrame:
    """
    Build the model input DataFrame from a fully-validated student dict.
    Returns a single-row pandas DataFrame with named columns matching
    FEATURE_ORDER — eliminates the scikit-learn feature-name warning that
    occurs when a nameless NumPy array is passed to a model trained on a
    named DataFrame.
    """
    input_data = [cleaned[f] for f in FEATURE_ORDER]

    if len(input_data) != len(FEATURE_ORDER):
        raise ValueError(
            f"Feature mismatch: expected {len(FEATURE_ORDER)}, got {len(input_data)}."
        )

    # Return a named DataFrame instead of a raw NumPy array so that
    # scikit-learn can match feature names and suppress the warning.
    return pd.DataFrame([input_data], columns=FEATURE_ORDER)


def _compute_derived(cleaned: dict) -> dict:
    """
    Compute engagement_score and academic_score for logging and future model use.
    Not currently part of the feature vector.
    """
    engagement_score = (
        cleaned["class_participation"]
        + cleaned["doubt_asking"]
        + cleaned["attention_level"]
        + cleaned["behaviour"]
    ) / 4.0

    academic_score = (
        cleaned["mid_term_marks"]
        + cleaned["class_test_score"]
        + cleaned["quiz_avg_score"]
    ) / 3.0

    return {
        "engagement_score": round(engagement_score, 4),
        "academic_score":   round(academic_score, 4),
    }


def _recommended_action(prediction: str) -> str:
    mapping = {
        "Weak":     "Remedial classes needed",
        "Average":  "Improvement guidance required",
        "Advanced": "Advanced learning recommended",
    }
    return mapping.get(prediction, "Further assessment required")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def predict_category(raw_data: dict) -> tuple:
    """
    Run validation → feature extraction → model prediction.

    Parameters
    ----------
    raw_data : dict
        Accepts both legacy keys and new canonical keys.

    Returns
    -------
    tuple : (prediction: str, confidence: float, recommended_action: str)
        prediction         — 'Weak' | 'Average' | 'Advanced' | 'Invalid'
        confidence         — percentage float, e.g. 87.3  (0.0 on error)
        recommended_action — short action string for teachers
    """
    if _model is None:
        logger.error("predict_category called but model is not loaded.")
        return "Unknown", 0.0, "Model not loaded"

    # 1. Normalise legacy aliases
    normalised = _normalise_keys(raw_data)

    # 2. Validate and sanitise all fields
    result = validate_student_data(normalised)
    cleaned = result.cleaned

    # Hard reject: structurally invalid input never reaches the model
    if not result.is_valid:
        logger.warning(
            "Rejected invalid input for student '%s': %s",
            raw_data.get("student_id", "<unknown>"),
            result.errors,
        )
        return "Invalid", 0.0, "Invalid input data — record rejected before prediction"

    if result.warnings:
        logger.debug(
            "Validation warnings for student '%s': %s",
            raw_data.get("student_id", "<unknown>"),
            result.warnings,
        )

    # 3. Compute derived features (logged; not yet in feature vector)
    derived = _compute_derived(cleaned)
    logger.debug("Derived features: %s", derived)

    # 4. Build named DataFrame feature vector (suppresses scikit-learn warning)
    X = _build_feature_vector(cleaned)

    # 5. Predict — X is now a named DataFrame, matching training-time feature names
    prediction    = _model.predict(X)[0]
    probabilities = _model.predict_proba(X)[0]
    confidence    = round(float(max(probabilities)) * 100, 2)
    action        = _recommended_action(prediction)

    logger.debug(
        "\n----- PREDICTION DEBUG -----\n"
        "  Student     : %s\n"
        "  Cleaned data: %s\n"
        "  Derived     : %s\n"
        "  Feature vec : %s\n"
        "  Prediction  : %s\n"
        "  Confidence  : %.2f%%\n"
        "----------------------------",
        raw_data.get("student_id", "<unknown>"),
        cleaned, derived, X.values.tolist(),   # .values.tolist() since X is now a DataFrame
        prediction, confidence,
    )

    return prediction, confidence, action