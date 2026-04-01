"""
ml_pipeline/train_model.py
---------------------------
Trains a RandomForestClassifier on the canonical 12-feature set and saves
the fitted model to models/model.pkl using joblib.

Feature set (order MUST match prediction_service.FEATURE_ORDER):
    attendance, mid_term_marks, class_test_score, quiz_avg_score,
    assignment_completion, assignment_delay, previous_sem_gpa, backlogs,
    class_participation, doubt_asking, attention_level, behaviour
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
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
# Synthetic data generation
# ---------------------------------------------------------------------------

def generate_data(n: int = 2000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    attendance            = rng.uniform(30, 100, n)
    mid_term_marks        = rng.uniform(10, 100, n)
    class_test_score      = rng.uniform(10, 100, n)
    quiz_avg_score        = rng.uniform(10, 100, n)
    assignment_completion = rng.uniform(20, 100, n)
    assignment_delay      = rng.integers(0, 15, n).astype(float)
    previous_sem_gpa      = rng.uniform(2.0, 10.0, n)
    backlogs              = rng.integers(0, 6, n).astype(float)
    class_participation   = rng.integers(0, 3, n)
    doubt_asking          = rng.integers(0, 3, n)
    attention_level       = rng.integers(0, 3, n)
    behaviour             = rng.integers(0, 3, n)

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

    def assign_label(row):
        # Academic component (dominant signal)
        academic = (
            row["attendance"]            * 0.15 +
            row["mid_term_marks"]        * 0.25 +
            row["class_test_score"]      * 0.15 +
            row["quiz_avg_score"]        * 0.10 +
            row["assignment_completion"] * 0.10 +
            row["previous_sem_gpa"]      * 3.0
        )
        # Engagement boost
        engagement = (
            row["class_participation"] +
            row["doubt_asking"]        +
            row["attention_level"]     +
            row["behaviour"]
        ) * 1.5

        # Penalty
        penalty = (
            row["assignment_delay"] * 0.8 +
            row["backlogs"]         * 5.0
        )

        score = academic + engagement - penalty

        # FIX: lowered thresholds to increase Advanced sample count
        # Old: score < 55 → Weak, score < 80 → Average, else → Advanced
        # New: score < 50 → Weak, score < 72 → Average, else → Advanced
        if score < 50:
            return "Weak"
        elif score < 72:
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

    model = RandomForestClassifier(
        n_estimators=200,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced",
    )
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

    importances = sorted(
        zip(FEATURE_ORDER, model.feature_importances_),
        key=lambda x: x[1], reverse=True
    )
    print("Feature Importances (ranked):")
    for feat, imp in importances:
        bar = "#" * int(imp * 40)
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
        mf.write("Feature Importances:\n")
        for feat, imp in importances:
            mf.write(f"  {feat}: {imp:.4f}\n")

    print("Metrics log  -> " + os.path.abspath(metrics_path))
    print("\nDone.")


if __name__ == "__main__":
    train()