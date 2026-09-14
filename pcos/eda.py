# -*- coding: utf-8 -*-
"""Exploratory data analysis for the PCOS dataset.

``run_eda`` prints a text summary and writes a set of figures to ``figures/``:

* ``01_target_balance.png``      - class distribution of PCOS (Y/N)
* ``02_missing_values.png``      - missing values per column (raw sheet)
* ``03_correlation_heatmap.png`` - full numeric correlation matrix
* ``04_target_correlation.png``  - features ranked by |correlation| with PCOS
* ``05_key_feature_boxplots.png``- top features split by PCOS status
* ``06_feature_histograms.png``  - distribution of every numeric feature
"""

from __future__ import annotations

import os
import textwrap

import matplotlib

matplotlib.use("Agg")  # headless: write files, never open a window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from .data import TARGET, load_clean_data, load_raw_data

sns.set_theme(style="whitegrid")

FIGURES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "figures"
)


def _save(fig, name: str, outdir: str) -> str:
    path = os.path.join(outdir, name)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def _section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def run_eda(outdir: str = FIGURES_DIR) -> pd.DataFrame:
    """Run the full EDA. Returns the cleaned dataframe."""
    os.makedirs(outdir, exist_ok=True)
    raw = load_raw_data()
    df = load_clean_data()

    _section("1. SHAPE & COLUMNS")
    print(f"Raw sheet 'Full_new'      : {raw.shape[0]} rows x {raw.shape[1]} columns")
    print(f"After cleaning            : {df.shape[0]} rows x {df.shape[1]} columns")
    print(f"Dropped identifier/junk   : Sl. No, Patient File No., Unnamed: 44")
    print("\nColumns kept:")
    print(textwrap.fill(", ".join(df.columns), width=100))

    _section("2. TARGET BALANCE  (PCOS (Y/N))")
    counts = df[TARGET].value_counts().sort_index()
    for k, v in counts.items():
        label = "PCOS" if k == 1 else "no PCOS"
        print(f"  {k} ({label:<7}): {v:>4}  ({v / len(df) * 100:5.1f}%)")
    print(f"  imbalance ratio        : {counts.max() / counts.min():.2f} : 1")

    fig, ax = plt.subplots(figsize=(5, 4))
    sns.countplot(x=df[TARGET], hue=df[TARGET], palette="Set2", legend=False, ax=ax)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["No PCOS (0)", "PCOS (1)"])
    ax.set_title("Target class distribution")
    ax.set_xlabel("")
    for c in ax.containers:
        ax.bar_label(c)
    print("saved:", _save(fig, "01_target_balance.png", outdir))

    _section("3. MISSING VALUES  (raw sheet, before coercion)")
    raw2 = raw.copy()
    raw2.columns = [" ".join(str(c).split()) for c in raw2.columns]
    # count text cells that will not parse as numbers, plus true NaNs
    miss = {}
    for col in raw2.columns:
        na = raw2[col].isna().sum()
        if raw2[col].dtype == object:
            na += (pd.to_numeric(raw2[col], errors="coerce").isna() & raw2[col].notna()).sum()
        if na:
            miss[col] = int(na)
    if miss:
        for col, n in sorted(miss.items(), key=lambda kv: -kv[1]):
            print(f"  {col:<28}: {n}")
    else:
        print("  none")

    fig, ax = plt.subplots(figsize=(7, 4))
    if miss:
        s = pd.Series(miss).sort_values()
        s.plot.barh(ax=ax, color="salmon")
        ax.set_xlabel("missing / unparseable values")
    else:
        ax.text(0.5, 0.5, "No missing values", ha="center", va="center")
        ax.set_axis_off()
    ax.set_title("Missing values per column")
    print("saved:", _save(fig, "02_missing_values.png", outdir))

    _section("4. DESCRIPTIVE STATISTICS")
    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(df.describe().T[["mean", "std", "min", "50%", "max"]].round(2))

    _section("5. IMPLAUSIBLE VALUES & OUTLIERS")
    # Physiologically impossible readings -> data-entry errors.
    plausible = {
        "Pulse rate(bpm)": (40, 160),
        "RR (breaths/min)": (8, 40),
        "BP _Systolic (mmHg)": (80, 220),
        "BP _Diastolic (mmHg)": (40, 140),
        "Hb(g/dl)": (5, 20),
        "BMI": (12, 60),
    }
    print("Readings outside a physiologically plausible range:")
    any_impossible = False
    for col, (lo, hi) in plausible.items():
        if col in df.columns:
            bad = df[(df[col] < lo) | (df[col] > hi)][col]
            if len(bad):
                any_impossible = True
                print(f"  {col:<24} outside [{lo}, {hi}]: {bad.tolist()}")
    if not any_impossible:
        print("  none")

    # Generic IQR outlier count for continuous features.
    print("\nIQR outliers (value < Q1-1.5*IQR or > Q3+1.5*IQR):")
    cont = [c for c in df.columns if c != TARGET and df[c].nunique() > 10]
    iqr_counts = {}
    for col in cont:
        q1, q3 = df[col].quantile([0.25, 0.75])
        iqr = q3 - q1
        n = int(((df[col] < q1 - 1.5 * iqr) | (df[col] > q3 + 1.5 * iqr)).sum())
        if n:
            iqr_counts[col] = n
    for col, n in sorted(iqr_counts.items(), key=lambda kv: -kv[1])[:12]:
        print(f"  {col:<24}: {n:>3}  ({n / len(df) * 100:4.1f}%)")
    print("\nNote: hormone assays (beta-HCG, FSH, LH, AMH, PRL, Vit D3) are"
          " genuinely right-skewed; median imputation + scaling is used so"
          " these extreme-but-real values do not dominate distance metrics.")

    _section("6. CORRELATION WITH TARGET")
    corr = df.corr(numeric_only=True)
    target_corr = corr[TARGET].drop(TARGET).sort_values(key=np.abs, ascending=False)
    print("Top 15 features by |correlation| with PCOS (Y/N):")
    for name, val in target_corr.head(15).items():
        print(f"  {name:<28}: {val:+.3f}")

    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(corr, cmap="coolwarm", center=0, square=True,
                cbar_kws={"shrink": 0.6}, ax=ax)
    ax.set_title("Numeric feature correlation matrix")
    print("saved:", _save(fig, "03_correlation_heatmap.png", outdir))

    fig, ax = plt.subplots(figsize=(7, 6))
    top = target_corr.head(15).iloc[::-1]
    colors = ["#d95f5f" if v > 0 else "#4c72b0" for v in top]
    top.plot.barh(ax=ax, color=colors)
    ax.set_xlabel("Pearson correlation with PCOS (Y/N)")
    ax.set_title("Features most associated with PCOS")
    print("saved:", _save(fig, "04_target_correlation.png", outdir))

    _section("7. KEY FEATURES BY PCOS STATUS")
    key = [c for c in target_corr.head(6).index]
    print("Comparing means (no PCOS vs PCOS):")
    grp = df.groupby(TARGET)[key].mean().T
    grp.columns = ["no PCOS", "PCOS"]
    print(grp.round(2))

    ncol = 3
    nrow = int(np.ceil(len(key) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(5 * ncol, 4 * nrow))
    for ax, col in zip(np.ravel(axes), key):
        sns.boxplot(x=df[TARGET], y=df[col], hue=df[TARGET],
                    palette="Set2", legend=False, ax=ax)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["No PCOS", "PCOS"])
        ax.set_title(col)
        ax.set_xlabel("")
    for ax in np.ravel(axes)[len(key):]:
        ax.set_axis_off()
    fig.suptitle("Top correlated features split by PCOS status", y=1.02)
    print("saved:", _save(fig, "05_key_feature_boxplots.png", outdir))

    _section("8. FEATURE DISTRIBUTIONS")
    feats = [c for c in df.columns if c != TARGET]
    ncol = 5
    nrow = int(np.ceil(len(feats) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4 * ncol, 3 * nrow))
    for ax, col in zip(np.ravel(axes), feats):
        sns.histplot(df[col].dropna(), kde=True, ax=ax, color="#4c72b0")
        ax.set_title(col, fontsize=9)
        ax.set_xlabel("")
    for ax in np.ravel(axes)[len(feats):]:
        ax.set_axis_off()
    fig.suptitle("Distribution of every numeric feature", y=1.005)
    print("saved:", _save(fig, "06_feature_histograms.png", outdir))

    _section("EDA COMPLETE")
    print(f"6 figures written to: {outdir}")
    return df


if __name__ == "__main__":
    run_eda()
