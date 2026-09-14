# -*- coding: utf-8 -*-
"""Loading and cleaning of the PCOS dataset.

The workbook ``PCOS_data_without_infertility.xlsx`` has two sheets:

* ``Instructions`` - a short read-me (this is the sheet ``pd.read_excel``
  picks by default, which is why the original script failed).
* ``Full_new``     - the actual 541-row dataset used here.

Known quirks handled below:

* ``Sl. No`` / ``Patient File No.``      - row identifiers, not predictive.
* ``Unnamed: 44``                        - stray empty column (2 junk values).
* ``II    beta-HCG(mIU/mL)``             - stored as text, one value is ``"1.99."``.
* ``AMH(ng/mL)``                         - stored as text, one value is ``"a"``.
* ``Marraige Status (Yrs)`` / ``Fast food (Y/N)`` - one missing value each.
* Several column names carry leading/trailing whitespace.
"""

from __future__ import annotations

import os

import pandas as pd

DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "PCOS_data_without_infertility.xlsx",
)
SHEET_NAME = "Full_new"
TARGET = "PCOS (Y/N)"

# Columns that are identifiers or junk rather than measurements.
DROP_COLUMNS = ["Sl. No", "Patient File No.", "Unnamed: 44"]

# Columns Excel imported as text because of a single malformed cell.
TEXT_NUMERIC_COLUMNS = ["II    beta-HCG(mIU/mL)", "AMH(ng/mL)"]

# Binary / categorical yes-no style columns (already encoded as 0/1 in the file).
BINARY_COLUMNS = [
    "Pregnant(Y/N)",
    "Weight gain(Y/N)",
    "hair growth(Y/N)",
    "Skin darkening (Y/N)",
    "Hair loss(Y/N)",
    "Pimples(Y/N)",
    "Fast food (Y/N)",
    "Reg.Exercise(Y/N)",
]


def load_raw_data() -> pd.DataFrame:
    """Return the ``Full_new`` sheet exactly as stored (no cleaning)."""
    return pd.read_excel(DATA_FILE, sheet_name=SHEET_NAME)


def load_clean_data() -> pd.DataFrame:
    """Return the analysis-ready dataframe.

    All feature columns are numeric; ``TARGET`` is kept as 0/1. Missing values
    are left as ``NaN`` so that imputation can happen inside a cross-validated
    pipeline (see :mod:`pcos.model`).
    """
    df = load_raw_data()

    # Normalise column names (strip stray whitespace, collapse doubles).
    df.columns = [" ".join(str(c).split()) for c in df.columns]

    drop = [" ".join(c.split()) for c in DROP_COLUMNS if " ".join(c.split()) in df.columns]
    df = df.drop(columns=drop)

    for col in (" ".join(c.split()) for c in TEXT_NUMERIC_COLUMNS):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Everything should be numeric now; coerce anything left over defensively.
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.reset_index(drop=True)


def feature_columns(df: pd.DataFrame) -> list[str]:
    """Feature column names: every column except the target."""
    return [c for c in df.columns if c != TARGET]


def split_X_y(df: pd.DataFrame):
    """Return ``(X, y)`` with ``X`` a dataframe and ``y`` an int Series."""
    X = df[feature_columns(df)]
    y = df[TARGET].astype(int)
    return X, y
