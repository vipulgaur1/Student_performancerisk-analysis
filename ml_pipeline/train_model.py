"""
ml_pipeline/train_model.py
---------------------------
Trains a LogisticRegression pipeline on the canonical 12-feature set and saves
the fitted model to models/model.pkl using joblib.

Feature set (order MUST match prediction_service.FEATURE_ORDER):
    attendance, mid_term_marks, class_test_score, quiz_avg_score,
    assignment_completion, assignment_delay, previous_sem_gpa, backlogs,
    class_participation, doubt_asking, attention_level, behaviour

Dataset generation strategy (v2):
    Features are generated using a latent academic ability variable so that
    student profiles are internally consistent and realistic.  Independent
    uniform sampling (v1) produced impossible profiles (high GPA + 5 backlogs,
    low attendance + high quiz scores) and extreme class imbalance (~54% Weak /
    ~6% Advanced), which hurt macro F1 and engagement feature importance.

    v2 changes:
      - Beta(2.5, 2.5) latent ability drives all features coherently.
      - Engagement features (class_participation, doubt_asking, attention_level,
        behaviour) are correlated with ability so they carry real predictive signal.
      - Thresholds calibrated to ~34% Weak / ~40% Average / ~26% Advanced.
      - class_weight removed; class balance is addressed at data level instead.
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, classification_report, confusion_matrix
)

# ---------------------------------------------------------------------------
# Canonical feature order — must be identical to prediction_service.FEATURE_ORDER
# ---------------------------------------------------------------------------
FEATURE_ORDER = [
    "attendance",
    "mid_term_marks",
    "class_test_score",
    "quiz_avg_score",
    "assignment_completion",
    "assignment_delay",
    "previous_sem_gpa",
    "backlogs",
    "class_participation",
    "doubt_asking",
    "attention_level",
    "behaviour",
]


# ---------------------------------------------------------------------------
# Synthetic data generation  (v2 — correlated student profiles)
# ---------------------------------------------------------------------------

def generate_data(n: int = 2000, seed: int = 42) -> pd.DataFrame:
    """
    Generate n student records whose features are realistically correlated.

    Design rationale
    ----------------
    v1 drew every feature independently with rng.uniform / rng.integers, which
    produced absurd profiles (GPA 9.0 + 5 backlogs, attendance 35% + quiz 90%)
    and left four engagement features with near-zero importance.

    v2 introduces a single latent variable, base_ability ~ Beta(2.5, 2.5),
    that drives all features in the same direction a real student's behaviour
    would:  strong ability → high attendance, high marks, low backlogs, and
    high engagement.  Each feature still has its own Gaussian noise term so
    borderline students exist naturally — the data is realistic, not perfect.

    Label thresholds (Weak < 40 ≤ Average < 68 ≤ Advanced) were calibrated
    against the generated score distribution to land at roughly
    34 % Weak / 40 % Average / 26 % Advanced, eliminating the previous
    54 % / 40 % / 6 % imbalance that crippled Advanced detection.
    """
    rng = np.random.default_rng(seed)

    # ── Latent academic ability ──────────────────────────────────────────────
    # Beta(2.5, 2.5) is symmetric and bell-shaped around 0.5, ranging [0, 1].
    # ~25 % of students land below 0.35 (Weak zone) and ~25 % above 0.65
    # (Advanced zone), giving a naturally balanced three-class distribution.
    base_ability = rng.beta(2.5, 2.5, n)

    # ── Continuous features ──────────────────────────────────────────────────
    # Pattern: feature = ability_slope * ability + intercept + noise
    # The intercept sets the realistic floor; the slope sets how much
    # ability lifts the feature; noise provides per-student variation.

    attendance = np.clip(
        base_ability * 55 + rng.normal(42, 8, n),
        30, 100
    )

    mid_term_marks = np.clip(
        base_ability * 70 + rng.normal(18, 10, n),
        10, 100
    )

    class_test_score = np.clip(
        base_ability * 68 + rng.normal(18, 10, n),
        10, 100
    )

    quiz_avg_score = np.clip(
        base_ability * 65 + rng.normal(18, 10, n),
        10, 100
    )

    assignment_completion = np.clip(
        base_ability * 60 + rng.normal(35, 8, n),
        20, 100
    )

    previous_sem_gpa = np.clip(
        base_ability * 7.0 + rng.normal(2.2, 0.6, n),
        2.0, 10.0
    )

    # Inverse relationship: weaker students submit later.
    # High ability → delay near 0–2 days; low ability → delay near 10–14 days.
    assignment_delay = np.clip(
        rng.normal(12 - base_ability * 11, 2, n),
        0, 14
    ).round().astype(float)

    # Inverse relationship: weaker students accumulate more backlogs.
    # Poisson mean scales from ~4.5 (ability=0) down to ~0 (ability=1).
    backlogs = np.clip(
        rng.poisson(np.maximum(0.05, (1 - base_ability) * 4.5)),
        0, 7
    ).astype(float)

    # ── Ordinal engagement features (0 / 1 / 2) ─────────────────────────────
    # Previously generated independently → importance ~0.
    # Now driven by ability with Gaussian noise so they carry real signal.
    # A strong student typically scores 1–2; a weak student typically 0–1.
    def _correlated_ordinal(ability_arr: np.ndarray, noise_std: float) -> np.ndarray:
        """Map ability [0,1] → ordinal {0,1,2} with realistic noise."""
        raw = ability_arr * 2.0 + rng.normal(0, noise_std, len(ability_arr))
        return np.clip(np.round(raw).astype(int), 0, 2)

    class_participation = _correlated_ordinal(base_ability, noise_std=0.40)
    doubt_asking        = _correlated_ordinal(base_ability, noise_std=0.45)
    attention_level     = _correlated_ordinal(base_ability, noise_std=0.40)
    behaviour           = _correlated_ordinal(base_ability, noise_std=0.35)

    df = pd.DataFrame({
        "attendance":            attendance,
        "mid_term_marks":        mid_term_marks,
        "class_test_score":      class_test_score,
        "quiz_avg_score":        quiz_avg_score,
        "assignment_completion": assignment_completion,
        "assignment_delay":      assignment_delay,
        "previous_sem_gpa":      previous_sem_gpa,
        "backlogs":              backlogs,
        "class_participation":   class_participation,
        "doubt_asking":          doubt_asking,
        "attention_level":       attention_level,
        "behaviour":             behaviour,
    })

    # ── Label assignment (same formula as v1, thresholds recalibrated) ───────
    # The scoring formula is unchanged so the model learns the same academic
    # logic.  Only the thresholds moved to match the new score distribution:
    #   Weak   < 40   (~34 % of samples)
    #   Average  40–67 (~40 % of samples)
    #   Advanced ≥ 68  (~26 % of samples)
    def assign_label(row):
        # Academic component — dominant signal
        academic = (
            row["attendance"]            * 0.15 +
            row["mid_term_marks"]        * 0.25 +
            row["class_test_score"]      * 0.15 +
            row["quiz_avg_score"]        * 0.10 +
            row["assignment_completion"] * 0.10 +
            row["previous_sem_gpa"]      * 3.0
        )
        # Engagement boost — now meaningful because features are correlated
        engagement = (
            row["class_participation"] +
            row["doubt_asking"]        +
            row["attention_level"]     +
            row["behaviour"]
        ) * 1.5

        # Penalty — weaker students naturally have higher values here
        penalty = (
            row["assignment_delay"] * 0.8 +
            row["backlogs"]         * 5.0
        )

        score = academic + engagement - penalty

        # Thresholds calibrated on the Beta(2.5,2.5)-driven distribution
        # to achieve ~34 % Weak / ~40 % Average / ~26 % Advanced.
        if score < 40:
            return "Weak"
        elif score < 68:
            return "Average"
        else:
            return "Advanced"

    df["label"] = df.apply(assign_label, axis=1)
    return df


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train():
    print("=" * 55)
    print("  Student Performance Model — Training")
    print("=" * 55)

    df = generate_data(n=2000, seed=42)
    print(f"\nDataset size : {len(df)} rows")
    print(f"Label distribution:\n{df['label'].value_counts().to_string()}\n")

    X = df[FEATURE_ORDER]
    y = df["label"]

    print("Features used (in model order):")
    for i, f in enumerate(FEATURE_ORDER, 1):
        print(f"  {i:2d}. {f}")
    print()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"Train size : {len(X_train)}   Test size : {len(X_test)}\n")

    # Logistic Regression pipeline: StandardScaler normalises the feature
    # magnitudes (attendance 30-100 vs behaviour 0-2) so the solver converges
    # reliably.  max_iter=1000 avoids ConvergenceWarning on this 12-feature set.
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("clf",    LogisticRegression(
            max_iter=1000,
            random_state=42,
            C=1.0,
        )),
    ])
    model.fit(X_train, y_train)

    # Save immediately after training
    model_dir  = os.path.join(os.path.dirname(__file__), "../models")
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, "model.pkl")
    joblib.dump(model, model_path)
    print("Model saved  -> " + os.path.abspath(model_path))

    y_pred = model.predict(X_test)

    acc  = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, average="weighted", zero_division=0)
    rec  = recall_score(y_test, y_pred, average="weighted", zero_division=0)
    f1   = f1_score(y_test, y_pred, average="weighted", zero_division=0)

    print("-" * 45)
    print("Hold-out Test Metrics")
    print("-" * 45)
    print(f"  Accuracy  : {acc  * 100:.2f}%")
    print(f"  Precision : {prec * 100:.2f}%")
    print(f"  Recall    : {rec  * 100:.2f}%")
    print(f"  F1 Score  : {f1   * 100:.2f}%")
    print()
    print("Classification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))

    labels = sorted(y.unique())
    cm = confusion_matrix(y_test, y_pred, labels=labels)
    print("Confusion Matrix (rows=actual, cols=predicted):")
    print(f"  Labels : {labels}")
    print(f"  Matrix :\n{cm}\n")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy", n_jobs=-1)
    print("5-Fold CV Accuracy : {:.2f}% +/- {:.2f}%".format(
        cv_scores.mean() * 100, cv_scores.std() * 100))
    print()

    # For a Pipeline with LogisticRegression, extract mean |coef| across classes
    coef_matrix = model.named_steps["clf"].coef_   # shape (n_classes, n_features)
    mean_abs_coef = np.mean(np.abs(coef_matrix), axis=0)
    importances = sorted(
        zip(FEATURE_ORDER, mean_abs_coef),
        key=lambda x: x[1], reverse=True
    )
    print("Feature Coefficients — mean |coef| across classes (ranked):")
    for feat, imp in importances:
        bar = "#" * int(imp * 10)
        print(f"  {feat:<25} {imp:.4f}  {bar}")
    print()

    metrics_path = os.path.join(os.path.dirname(__file__), "metrics.txt")
    with open(metrics_path, "w", encoding="utf-8") as mf:
        mf.write("Student Performance Model — Training Metrics\n")
        mf.write("=" * 45 + "\n")
        mf.write(f"Dataset rows : {len(df)}\n")
        mf.write(f"Features     : {FEATURE_ORDER}\n\n")
        mf.write(f"Accuracy  : {acc  * 100:.2f}%\n")
        mf.write(f"Precision : {prec * 100:.2f}%\n")
        mf.write(f"Recall    : {rec  * 100:.2f}%\n")
        mf.write(f"F1 Score  : {f1   * 100:.2f}%\n\n")
        mf.write("CV (5-fold): {:.2f}% +/- {:.2f}%\n\n".format(
            cv_scores.mean() * 100, cv_scores.std() * 100))
        mf.write("Classification Report:\n")
        mf.write(classification_report(y_test, y_pred, zero_division=0))
        mf.write("\nConfusion Matrix:\n")
        mf.write(f"Labels : {labels}\n")
        mf.write(str(cm) + "\n\n")
        mf.write("Feature Coefficients (mean |coef|):\n")
        for feat, imp in importances:
            mf.write(f"  {feat}: {imp:.4f}\n")

    print("Metrics log  -> " + os.path.abspath(metrics_path))
    print("\nDone.")


if __name__ == "__main__":
    train()