# -*- coding: utf-8 -*-
"""Train the *symptom-only* PCOS model used by the web app.

The full model in :mod:`pcos.model` uses every column, including ultrasound
follicle counts. A person filling in a web form cannot supply those, so this
module trains a smaller KNN on 13 features a user can answer without any lab
work or scan:

    Age, Height, Weight, BMI, cycle regularity, cycle length,
    recent weight gain, excess hair growth, skin darkening, hair loss,
    acne, frequent fast food, regular exercise.

``train_and_save`` writes ``models/pcos_symptom_knn.joblib`` (a fitted
Pipeline) plus ``models/pcos_symptom_meta.json`` (feature order, input
ranges, held-out metrics and per-symptom association rates the app uses to
explain a result).
"""

from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .data import TARGET, load_clean_data

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(ROOT, "models")
MODEL_PATH = os.path.join(MODEL_DIR, "pcos_symptom_knn.joblib")
META_PATH = os.path.join(MODEL_DIR, "pcos_symptom_meta.json")

RANDOM_STATE = 42

# (raw dataframe column, form field id, kind). "binary" -> 0/1 toggle.
FIELDS = [
    ("Age (yrs)", "age", "number"),
    ("Height(Cm)", "height_cm", "number"),
    ("Weight (Kg)", "weight_kg", "number"),
    ("BMI", "bmi", "derived"),  # computed from height + weight
    ("Cycle(R/I)", "cycle_irregular", "cycle"),  # 2 = regular, 4/5 = irregular
    ("Cycle length(days)", "cycle_length", "number"),
    ("Weight gain(Y/N)", "weight_gain", "binary"),
    ("hair growth(Y/N)", "hair_growth", "binary"),
    ("Skin darkening (Y/N)", "skin_darkening", "binary"),
    ("Hair loss(Y/N)", "hair_loss", "binary"),
    ("Pimples(Y/N)", "pimples", "binary"),
    ("Fast food (Y/N)", "fast_food", "binary"),
    ("Reg.Exercise(Y/N)", "regular_exercise", "binary"),
]
FEATURE_COLUMNS = [col for col, _, _ in FIELDS]
BINARY_COLUMNS = [col for col, _, kind in FIELDS if kind == "binary"]


def _build_search(X_train, y_train) -> GridSearchCV:
    pipe = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("clf", KNeighborsClassifier()),
        ]
    )
    grid = {
        "clf__n_neighbors": list(range(3, 40, 2)),
        "clf__weights": ["uniform", "distance"],
        "clf__p": [1, 2],
    }
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    search = GridSearchCV(pipe, grid, cv=cv, scoring="accuracy", n_jobs=-1)
    search.fit(X_train, y_train)
    return search


def _symptom_association(df: pd.DataFrame) -> dict:
    """For each yes/no symptom: how common it is in each group.

    Returns ``{col: {"pcos_rate": .., "no_pcos_rate": .., "lift": ..}}`` where
    ``lift`` is ``pcos_rate / overall_rate`` (>1 means "more common in PCOS").
    """
    out = {}
    overall = df[TARGET].mean()
    for col in BINARY_COLUMNS:
        has = df[df[col] == 1]
        pcos_rate = float(has[TARGET].mean()) if len(has) else overall
        out[col] = {
            "pcos_given_symptom": round(pcos_rate, 3),
            "baseline_pcos_rate": round(float(overall), 3),
            "lift": round(pcos_rate / overall, 2) if overall else 1.0,
        }
    return out


def train_and_save() -> dict:
    os.makedirs(MODEL_DIR, exist_ok=True)
    df = load_clean_data()
    X = df[FEATURE_COLUMNS]
    y = df[TARGET].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
    )
    search = _build_search(X_train, y_train)
    model = search.best_estimator_

    y_pred = model.predict(X_test)
    y_score = model.predict_proba(X_test)[:, 1]
    metrics = {
        "cv_accuracy": round(float(search.best_score_), 4),
        "test_accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "test_precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        "test_recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
        "test_f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
        "test_roc_auc": round(float(roc_auc_score(y_test, y_score)), 4),
        "test_size": int(len(y_test)),
    }

    # Refit on ALL data so the shipped model uses every record.
    model.fit(X, y)

    import joblib

    joblib.dump(model, MODEL_PATH)

    ranges = {
        col: {
            "min": float(np.nanmin(df[col])),
            "max": float(np.nanmax(df[col])),
            "median": float(np.nanmedian(df[col])),
        }
        for col in ["Age (yrs)", "Height(Cm)", "Weight (Kg)", "Cycle length(days)"]
    }

    meta = {
        "fields": [
            {"column": col, "field": fid, "kind": kind} for col, fid, kind in FIELDS
        ],
        "feature_columns": FEATURE_COLUMNS,
        "binary_columns": BINARY_COLUMNS,
        "best_params": {k.replace("clf__", ""): v for k, v in search.best_params_.items()},
        "metrics": metrics,
        "n_samples": int(len(df)),
        "class_balance": {
            "no_pcos": int((y == 0).sum()),
            "pcos": int((y == 1).sum()),
        },
        "input_ranges": ranges,
        "symptom_association": _symptom_association(df),
    }
    with open(META_PATH, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    return meta


if __name__ == "__main__":
    m = train_and_save()
    print("Saved model  ->", MODEL_PATH)
    print("Saved meta   ->", META_PATH)
    print("Best params  :", m["best_params"])
    print("Metrics      :")
    for k, v in m["metrics"].items():
        print(f"  {k:16}: {v}")
