# -*- coding: utf-8 -*-
"""Model selection and evaluation for PCOS prediction.

Workflow (see :func:`run`):

1. Clean data -> stratified 80/20 train/test split.
2. Compare several classifiers with 5-fold stratified cross-validation on the
   training set (median imputation + standard scaling inside every fold, so
   there is no leakage).
3. Tune K-Nearest-Neighbours with ``GridSearchCV`` (KNN is the preferred model).
4. Refit the tuned KNN on the full training set and report accuracy - plus
   precision / recall / F1 / ROC-AUC and the confusion matrix - on the
   untouched test set.
"""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_score, train_test_split
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from .data import load_clean_data, split_X_y

FIGURES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "figures"
)
RANDOM_STATE = 42
CV = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)


def make_pipeline(estimator) -> Pipeline:
    """Impute (median) -> scale -> estimator."""
    return Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("clf", estimator),
        ]
    )


def candidate_models() -> dict:
    return {
        "KNN": KNeighborsClassifier(),
        "Logistic Regression": LogisticRegression(max_iter=2000, random_state=RANDOM_STATE),
        "SVM (RBF)": SVC(random_state=RANDOM_STATE),
        "Random Forest": RandomForestClassifier(n_estimators=300, random_state=RANDOM_STATE),
        "Gaussian NB": GaussianNB(),
    }


def compare_models(X_train, y_train) -> pd.DataFrame:
    """5-fold CV accuracy for every candidate model."""
    rows = []
    for name, est in candidate_models().items():
        scores = cross_val_score(
            make_pipeline(est), X_train, y_train, cv=CV, scoring="accuracy"
        )
        rows.append(
            {"model": name, "cv_accuracy_mean": scores.mean(), "cv_accuracy_std": scores.std()}
        )
    return (
        pd.DataFrame(rows)
        .sort_values("cv_accuracy_mean", ascending=False)
        .reset_index(drop=True)
    )


def tune_knn(X_train, y_train) -> GridSearchCV:
    """Grid-search KNN hyper-parameters with 5-fold CV."""
    pipe = make_pipeline(KNeighborsClassifier())
    grid = {
        "clf__n_neighbors": list(range(3, 32, 2)),
        "clf__weights": ["uniform", "distance"],
        "clf__p": [1, 2],  # Manhattan / Euclidean
    }
    search = GridSearchCV(pipe, grid, cv=CV, scoring="accuracy", n_jobs=-1)
    search.fit(X_train, y_train)
    return search


def evaluate_on_test(model, X_test, y_test, outdir: str = FIGURES_DIR) -> dict:
    """Score a fitted model on the held-out test set and save a confusion matrix."""
    os.makedirs(outdir, exist_ok=True)
    y_pred = model.predict(X_test)
    try:
        y_score = model.predict_proba(X_test)[:, 1]
        auc = roc_auc_score(y_test, y_score)
    except (AttributeError, ValueError):
        auc = float("nan")

    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "roc_auc": auc,
    }

    fig, ax = plt.subplots(figsize=(4.5, 4))
    ConfusionMatrixDisplay(
        confusion_matrix(y_test, y_pred), display_labels=["No PCOS", "PCOS"]
    ).plot(ax=ax, cmap="Blues", colorbar=False)
    ax.set_title("KNN - test-set confusion matrix")
    path = os.path.join(outdir, "07_knn_confusion_matrix.png")
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)

    return {"metrics": metrics, "report": classification_report(y_test, y_pred,
            target_names=["No PCOS", "PCOS"], zero_division=0), "figure": path}


def run(outdir: str = FIGURES_DIR) -> dict:
    df = load_clean_data()
    X, y = split_X_y(df)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
    )

    print("=" * 70)
    print("MODEL COMPARISON  -  5-fold stratified CV on the training set")
    print("=" * 70)
    table = compare_models(X_train, y_train)
    for _, r in table.iterrows():
        print(f"  {r['model']:<22}: {r['cv_accuracy_mean'] * 100:6.2f}%  "
              f"(+/- {r['cv_accuracy_std'] * 100:.2f})")
    best_overall = table.iloc[0]["model"]
    print(f"\nBest by CV accuracy   : {best_overall}")

    print("\n" + "=" * 70)
    print("TUNING KNN  (preferred model)")
    print("=" * 70)
    search = tune_knn(X_train, y_train)
    print(f"  best params           : {search.best_params_}")
    print(f"  best CV accuracy       : {search.best_score_ * 100:.2f}%")

    result = evaluate_on_test(search.best_estimator_, X_test, y_test, outdir)
    m = result["metrics"]

    print("\n" + "=" * 70)
    print(f"FINAL MODEL: tuned KNN  -  held-out test set ({len(y_test)} patients)")
    print("=" * 70)
    print(f"  Accuracy              : {m['accuracy'] * 100:.2f}%")
    print(f"  Precision             : {m['precision'] * 100:.2f}%")
    print(f"  Recall (sensitivity)  : {m['recall'] * 100:.2f}%")
    print(f"  F1 score              : {m['f1'] * 100:.2f}%")
    print(f"  ROC-AUC               : {m['roc_auc']:.3f}")
    print("\n" + result["report"])
    print(f"confusion matrix saved to: {result['figure']}")

    print("\n" + "#" * 70)
    print(f"#  CHOSEN MODEL: KNN ({search.best_params_})")
    print(f"#  TEST ACCURACY: {m['accuracy'] * 100:.2f}%")
    print("#" * 70)

    return {
        "comparison": table,
        "knn_best_params": search.best_params_,
        "knn_cv_accuracy": search.best_score_,
        "test_metrics": m,
    }


if __name__ == "__main__":
    run()
