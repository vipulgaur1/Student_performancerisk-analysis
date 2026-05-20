"""
ml_pipeline/compare_models.py
------------------------------
Fair comparison of Decision Tree, Random Forest, and Logistic Regression
on the canonical SEPPS dataset — the same data, labels, features, and
split that train_model.py uses for the deployed model.

Previous version used students_400.csv and a GPA-derived risk_level target,
which made comparison unfair:
  - Different target variable (risk_level vs Weak/Average/Advanced)
  - previous_sem_gpa had to be dropped to avoid leakage, removing the
    single strongest predictor and artificially handicapping every model
  - Only 320 training rows (4x smaller than the canonical 1600-row split)
  - Decision Tree ran with default hyperparameters, not the deployed config

This version corrects all of that:
  - Identical dataset: generate_data(n=2000, seed=42) from train_model.py
  - Identical labels: Weak / Average / Advanced
  - Identical feature set: FEATURE_ORDER (12 features, no drops)
  - Identical split: 80/20 stratified, random_state=42
  - Decision Tree uses the exact deployed hyperparameters
  - All models evaluated with both hold-out metrics and 5-fold CV
  - Macro F1 included so class-balanced performance is visible
"""

import sys
from pathlib import Path

# Allow importing generate_data and FEATURE_ORDER from the sibling module
# without requiring an installed package or modifying PYTHONPATH externally.
_ML_DIR = Path(__file__).resolve().parent
if str(_ML_DIR) not in sys.path:
    sys.path.insert(0, str(_ML_DIR))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from train_model import FEATURE_ORDER, generate_data


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

def load_dataset() -> tuple[pd.DataFrame, pd.Series]:
    """
    Generate the canonical SEPPS training dataset using the same function and
    parameters as train_model.py.  Returns (X, y) ready for splitting.
    """
    df = generate_data(n=2000, seed=42)
    X  = df[FEATURE_ORDER]
    y  = df["label"]
    return X, y


# ---------------------------------------------------------------------------
# Model definitions
# ---------------------------------------------------------------------------

def build_models() -> dict:
    """
    Return all three models to compare.

    Decision Tree
        Uses the exact hyperparameters of the deployed model in train_model.py
        so the comparison reflects actual production performance, not a default
        tree that would overfit differently.

    Random Forest
        Ensemble of 300 trees with the same per-tree depth and leaf constraints
        as the Decision Tree, so depth is a controlled variable between the two
        tree-based models.  No class_weight: the dataset is balanced at the
        generation level (~34/40/26 %).

    Logistic Regression
        Wrapped in a Pipeline with StandardScaler because LR is sensitive to
        feature scale and the 12 features span very different numeric ranges
        (GPA 2–10 vs mid_term 10–100).  Without scaling LR would be unfair.
        No class_weight for the same reason as Random Forest.
    """
    # ── Deployed Decision Tree (exact replica of train_model.py config) ──────
    decision_tree = DecisionTreeClassifier(
        max_depth=8,
        min_samples_split=10,
        min_samples_leaf=4,
        random_state=42,
    )

    # ── Random Forest ─────────────────────────────────────────────────────────
    random_forest = RandomForestClassifier(
        n_estimators=300,
        max_depth=8,           # same depth cap as Decision Tree
        min_samples_split=10,  # same leaf constraints
        min_samples_leaf=4,
        random_state=42,
    )

    # ── Logistic Regression (needs feature scaling) ───────────────────────────
    logistic_regression = Pipeline(steps=[
        ("scaler", StandardScaler()),
        ("model",  LogisticRegression(
            max_iter=1000,
            random_state=42,
            solver="lbfgs",   # lbfgs handles multinomial natively in sklearn>=1.5
        )),
    ])

    return {
        "Decision Tree":      decision_tree,
        "Random Forest":      random_forest,
        "Logistic Regression": logistic_regression,
    }


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def evaluate_hold_out(model, X_test: pd.DataFrame, y_test: pd.Series,
                      labels: list) -> tuple[dict, pd.DataFrame]:
    """Return scalar metrics dict and a confusion-matrix DataFrame."""
    y_pred = model.predict(X_test)

    metrics = {
        "Accuracy":        accuracy_score(y_test, y_pred),
        "Precision (W)":   precision_score(y_test, y_pred, average="weighted",
                                            zero_division=0),
        "Recall (W)":      recall_score(y_test, y_pred, average="weighted",
                                         zero_division=0),
        "F1 (weighted)":   f1_score(y_test, y_pred, average="weighted",
                                     zero_division=0),
        "F1 (macro)":      f1_score(y_test, y_pred, average="macro",
                                     zero_division=0),
    }

    cm = confusion_matrix(y_test, y_pred, labels=labels)
    cm_df = pd.DataFrame(
        cm,
        index=[f"Actual — {lbl}" for lbl in labels],
        columns=[f"Pred — {lbl}" for lbl in labels],
    )

    report = classification_report(y_test, y_pred, zero_division=0)

    return metrics, cm_df, report


def run_cross_validation(model, X: pd.DataFrame, y: pd.Series) -> tuple[float, float]:
    """5-fold stratified CV; returns (mean_accuracy, std_accuracy)."""
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy", n_jobs=-1)
    return scores.mean(), scores.std()


def print_model_results(name: str, metrics: dict, cm_df: pd.DataFrame,
                         report: str, cv_mean: float, cv_std: float) -> None:
    bar = "=" * 70
    print(f"\n{bar}")
    print(f"  {name}")
    print(bar)
    print("  Hold-out metrics:")
    for k, v in metrics.items():
        print(f"    {k:<18s}: {v:.4f}")
    print(f"  5-Fold CV Accuracy : {cv_mean*100:.2f}% +/- {cv_std*100:.2f}%")
    print("\n  Per-class breakdown (hold-out):")
    for line in report.splitlines():
        print("    " + line)
    print("\n  Confusion Matrix (hold-out):")
    with pd.option_context("display.max_columns", None, "display.width", 140):
        for line in cm_df.to_string().splitlines():
            print("    " + line)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("  SEPPS — Model Comparison")
    print("  Dataset : generate_data(n=2000, seed=42)  [same as train_model.py]")
    print("  Labels  : Weak / Average / Advanced")
    print("  Split   : 80 % train / 20 % test, stratified, random_state=42")
    print("=" * 70)

    # ── 1. Load dataset ───────────────────────────────────────────────────────
    X, y = load_dataset()
    print(f"\nDataset size : {len(X)} rows  |  Features : {len(FEATURE_ORDER)}")
    print("Label distribution:")
    for label, count in y.value_counts().items():
        print(f"  {label:<10s}: {count:5d}  ({count/len(y)*100:.1f}%)")

    # ── 2. Train / test split ─────────────────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"\nTrain rows : {len(X_train)}   Test rows : {len(X_test)}")

    labels = sorted(y.unique())   # ['Advanced', 'Average', 'Weak']

    # ── 3. Train, evaluate, cross-validate each model ────────────────────────
    models        = build_models()
    summary_rows  = []

    for name, model in models.items():
        print(f"\nTraining {name} ...")
        model.fit(X_train, y_train)

        metrics, cm_df, report = evaluate_hold_out(model, X_test, y_test, labels)
        cv_mean, cv_std         = run_cross_validation(model, X, y)

        print_model_results(name, metrics, cm_df, report, cv_mean, cv_std)

        summary_rows.append({
            "Model":           name,
            "Accuracy":        metrics["Accuracy"],
            "Precision (W)":   metrics["Precision (W)"],
            "Recall (W)":      metrics["Recall (W)"],
            "F1 (weighted)":   metrics["F1 (weighted)"],
            "F1 (macro)":      metrics["F1 (macro)"],
            "CV Acc (mean)":   cv_mean,
            "CV Acc (std)":    cv_std,
        })

    # ── 4. Summary comparison table ───────────────────────────────────────────
    summary = (
        pd.DataFrame(summary_rows)
        .sort_values("F1 (macro)", ascending=False)
        .reset_index(drop=True)
    )

    print("\n" + "=" * 70)
    print("  Final Model Comparison  (sorted by macro F1)")
    print("=" * 70)
    float_cols = ["Accuracy", "Precision (W)", "Recall (W)",
                  "F1 (weighted)", "F1 (macro)", "CV Acc (mean)", "CV Acc (std)"]
    fmt = {c: lambda v: f"{v:.4f}" for c in float_cols}
    print(summary.to_string(index=False, formatters=fmt))

    # ── 5. Winner ─────────────────────────────────────────────────────────────
    best = summary.iloc[0]
    print(f"\nBest model by macro F1  : {best['Model']}")
    print(f"  Macro F1              : {best['F1 (macro)']:.4f}")
    print(f"  Weighted F1           : {best['F1 (weighted)']:.4f}")
    print(f"  Accuracy              : {best['Accuracy']:.4f}")
    print(f"  5-Fold CV             : {best['CV Acc (mean)']*100:.2f}% "
          f"+/- {best['CV Acc (std)']*100:.2f}%")

    # ── 6. Decision Tree deployment note ──────────────────────────────────────
    dt_row = summary[summary["Model"] == "Decision Tree"].iloc[0]
    best_f1_macro = best["F1 (macro)"]
    dt_f1_macro   = dt_row["F1 (macro)"]
    gap           = best_f1_macro - dt_f1_macro

    print("\nDeployment note:")
    if gap < 0.02:
        print(
            f"  Decision Tree (macro F1 = {dt_f1_macro:.4f}) is within {gap*100:.2f} pp "
            f"of the best model.\n"
            "  It remains the recommended deployment choice for SEPPS:\n"
            "  interpretable, fast, and without any additional dependencies."
        )
    else:
        print(
            f"  Decision Tree macro F1 ({dt_f1_macro:.4f}) trails the best model "
            f"by {gap*100:.2f} pp.\n"
            f"  Consider whether the accuracy gain justifies losing interpretability."
        )


if __name__ == "__main__":
    main()
