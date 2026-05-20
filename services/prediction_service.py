"""
services/prediction_service.py
--------------------------------
Loads the trained DecisionTree model and exposes predict_category() (single)
and predict_batch() (bulk -- use this for CSV upload and predict_all).

Flow -- single
--------------
raw_data  ->  alias normalisation
          ->  validation_service.validate_student_data()
          ->  _build_feature_vector()   (12 canonical features -> model input)
          ->  model.predict_proba  (one call, argmax -> label + confidence)
          ->  (prediction, confidence, recommended_action)

Flow -- batch (predict_batch)
------------------------------
list[raw_data]  ->  alias normalisation x N
                ->  validate_student_data x N
                ->  one multi-row DataFrame
                ->  one model.predict_proba(X) call for all N rows
                ->  list[(prediction, confidence, recommended_action)]

Feature set (12 canonical fields -- must match train_model.py FEATURE_ORDER):
    attendance, mid_term_marks, class_test_score, quiz_avg_score,
    assignment_completion, assignment_delay, previous_sem_gpa, backlogs,
    class_participation, doubt_asking, attention_level, behaviour
"""

import joblib
import logging
import os
import numpy as np
import pandas as pd

from services.validation_service import validate_student_data

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model loading -- runs once at import time; the loaded object is reused for
# every request.  No per-request joblib.load() calls.
# ---------------------------------------------------------------------------
MODEL_PATH = os.path.join(os.path.dirname(__file__), '../models/model.pkl')

try:
    _model = joblib.load(MODEL_PATH)
    logger.info("Model loaded successfully from %s", MODEL_PATH)
except Exception as _e:
    logger.error("Failed to load model: %s", _e)
    _model = None

# ---------------------------------------------------------------------------
# Canonical feature order -- single source of truth shared with train_model.py
# ---------------------------------------------------------------------------
FEATURE_ORDER = [
    "attendance",            # 0-100
    "mid_term_marks",        # 0-100
    "class_test_score",      # 0-100
    "quiz_avg_score",        # 0-100
    "assignment_completion", # 0-100
    "assignment_delay",      # numeric >= 0
    "previous_sem_gpa",      # 0-10
    "backlogs",              # numeric >= 0
    "class_participation",   # 0, 1, 2
    "doubt_asking",          # 0, 1, 2
    "attention_level",       # 0, 1, 2
    "behaviour",             # 0, 1, 2
]

# ---------------------------------------------------------------------------
# Legacy column alias map -- keeps old CSV uploads working transparently
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
    FEATURE_ORDER -- eliminates the scikit-learn feature-name warning that
    occurs when a nameless NumPy array is passed to a model trained on a
    named DataFrame.
    """
    input_data = [cleaned[f] for f in FEATURE_ORDER]

    if len(input_data) != len(FEATURE_ORDER):
        raise ValueError(
            f"Feature mismatch: expected {len(FEATURE_ORDER)}, got {len(input_data)}."
        )

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
# Single-record public API
# ---------------------------------------------------------------------------

def predict_category(raw_data: dict) -> tuple:
    """
    Run validation -> feature extraction -> model prediction for one student.

    Parameters
    ----------
    raw_data : dict
        Accepts both legacy keys and new canonical keys.

    Returns
    -------
    tuple : (prediction: str, confidence: float, recommended_action: str)
        prediction         -- 'Weak' | 'Average' | 'Advanced' | 'Invalid'
        confidence         -- percentage float, e.g. 87.3  (0.0 on error)
        recommended_action -- short action string for teachers
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
        return "Invalid", 0.0, "Invalid input data -- record rejected before prediction"

    if result.warnings:
        logger.debug(
            "Validation warnings for student '%s': %s",
            raw_data.get("student_id", "<unknown>"),
            result.warnings,
        )

    # 3. Compute derived features only when DEBUG logging is actually enabled.
    #    Guarding this avoids calling _compute_derived() on every call even when
    #    nobody is reading debug logs (saves ~0.05 ms per call).
    if logger.isEnabledFor(logging.DEBUG):
        derived = _compute_derived(cleaned)
        logger.debug("Derived features: %s", derived)
    else:
        derived = {}

    # 4. Build named DataFrame feature vector (suppresses scikit-learn warning)
    X = _build_feature_vector(cleaned)

    # 5. Single predict_proba() call -- label comes from argmax, no second
    #    model.predict() needed (Decision Tree traverses the tree once).
    probabilities = _model.predict_proba(X)[0]
    class_idx     = int(np.argmax(probabilities))
    prediction    = _model.classes_[class_idx]
    confidence    = round(float(probabilities[class_idx]) * 100, 2)
    action        = _recommended_action(prediction)

    if logger.isEnabledFor(logging.DEBUG):
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
            cleaned, derived, X.values.tolist(),
            prediction, confidence,
        )

    return prediction, confidence, action


# ---------------------------------------------------------------------------
# Batch public API -- use this for CSV upload and predict_all
# ---------------------------------------------------------------------------

def predict_batch(raw_data_list: list) -> list:
    """
    Predict categories for a list of student records in a SINGLE model call.

    This is the fast path for batch operations.  Compared with calling
    predict_category() 400 times it:
      - Builds one multi-row DataFrame instead of 400 single-row DataFrames
      - Makes one predict_proba() call instead of 400 separate calls
      - Eliminates 400x Python-loop overhead around model inference

    Parameters
    ----------
    raw_data_list : list of dict
        Each dict accepts both legacy and canonical field names.
        Empty list returns [].

    Returns
    -------
    list of tuple -- one entry per input row, preserving order:
        (prediction: str, confidence: float, recommended_action: str)
        Invalid rows return ('Invalid', 0.0, 'Invalid input data...').
    """
    if _model is None:
        return [("Unknown", 0.0, "Model not loaded")] * len(raw_data_list)

    if not raw_data_list:
        return []

    # 1. Normalise aliases for all rows (pure Python dict ops, fast)
    normalised_list = [_normalise_keys(r) for r in raw_data_list]

    # 2. Validate all rows; track which pass so results stay aligned
    results       = [None] * len(raw_data_list)
    valid_idx     = []   # original positions of valid rows
    valid_cleaned = []   # cleaned dicts for valid rows only

    for i, normalised in enumerate(normalised_list):
        vr = validate_student_data(normalised)
        if not vr.is_valid:
            results[i] = (
                "Invalid", 0.0,
                "Invalid input data -- record rejected before prediction",
            )
        else:
            valid_idx.append(i)
            valid_cleaned.append(vr.cleaned)

    if not valid_cleaned:
        return results

    # 3. Build ONE multi-row DataFrame for the entire valid batch.
    #    list-comprehension + single DataFrame() call avoids 400x constructor
    #    overhead that the old row-by-row path incurred.
    X = pd.DataFrame(
        [[row[f] for f in FEATURE_ORDER] for row in valid_cleaned],
        columns=FEATURE_ORDER,
    )

    # 4. Single predict_proba() call for all N rows at once.
    #    Decision Tree traversal is vectorised internally.
    proba_matrix  = _model.predict_proba(X)                   # (n_valid, n_classes)
    class_indices = np.argmax(proba_matrix, axis=1)
    predictions   = _model.classes_[class_indices]            # class labels
    confidences   = np.max(proba_matrix, axis=1) * 100.0      # percentages

    # 5. Map results back to original positions in the input list
    for batch_pos, orig_idx in enumerate(valid_idx):
        pred   = predictions[batch_pos]
        conf   = round(float(confidences[batch_pos]), 2)
        action = _recommended_action(pred)
        results[orig_idx] = (pred, conf, action)

    return results
