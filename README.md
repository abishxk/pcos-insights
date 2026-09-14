# PCOS Prediction

Predict Polycystic Ovary Syndrome (PCOS) from clinical, hormonal and
ultrasound measurements in `PCOS_data_without_infertility.xlsx` (541 patients,
sheet `Full_new`).

## Layout

| Path | Purpose |
|------|---------|
| `pcos/data.py`          | Load the correct sheet and clean it (drop IDs/junk, fix text-typed numeric columns, normalise column names). |
| `pcos/eda.py`           | Exploratory data analysis: prints a summary, writes 6 figures to `figures/`. |
| `pcos/model.py`         | Full-feature model comparison (5-fold stratified CV), KNN tuning, held-out test evaluation. |
| `pcos/symptom_model.py` | Trains the *symptom-only* KNN used by the web app (13 self-answerable inputs); saves to `models/`. |
| `PCOS.py`               | Entry point that runs EDA then modelling. |
| `app.py`                | Flask web app: routes for the landing page and the symptom tool. |
| `templates/landing.html`, `static/landing.*` | Full-bleed video-background landing page (`/`). "Get Started" opens the tool. |
| `templates/index.html`, `static/style.css`, `static/app.js` | The symptom questionnaire (`/app`). |

## Setup

```bash
pip install -r requirements.txt
```

## Run the analysis

```bash
python PCOS.py            # full pipeline (EDA + modelling)
python PCOS.py --no-eda   # modelling only
python -m pcos.eda        # EDA only
python -m pcos.model      # modelling only
```

## Run the web app

```bash
python -m pcos.symptom_model   # train + save the symptom model (once)
python app.py                  # http://127.0.0.1:5000
```

Routes: `/` is the landing page, `/app` is the symptom check, `POST /api/predict`
serves the model. The landing page pulls Inter, the BubbledotICG-FinePos display
face, Font Awesome and the background video from CDNs; drop a real
`static/fonts/GeistPixel-Circle.woff2` in place of the placeholder note and swap
`static/assets/logo.webp` for the real brand mark when available.

The page asks 13 questions a person can answer without lab work (age, height,
weight, cycle regularity and length, and yes/no symptoms). The result is stated
plainly: *"X% of the 23 dataset records most similar to your answers had a PCOS
diagnosis"* (that is what KNN computes), placed against the 33% dataset average,
with a lower / moderate / higher band. The reported symptoms are shown with a
correlation-not-causation note, and an expandable panel explains the data, the
model, its inputs and its accuracy. Front end is a single hand-authored HTML/CSS
page (no build step); `POST /api/predict` serves the model.

**Symptom-only model** (`GridSearchCV`-tuned KNN, `n_neighbors=23`,
`weights='distance'`): held-out accuracy **86.2%**, ROC-AUC **0.92** on 109
test patients. Lower than the full model below because it omits the ultrasound
follicle counts, which are the single strongest predictor.

## Data cleaning applied

* Read sheet `Full_new` (the default sheet is a read-me, which is why the
  original script failed).
* Drop `Sl. No`, `Patient File No.` (identifiers) and `Unnamed: 44` (empty).
* `II beta-HCG(mIU/mL)` and `AMH(ng/mL)` were imported as text because of a
  single malformed cell each (`"1.99."`, `"a"`) - coerced to numeric.
* One missing value each in `Marraige Status (Yrs)` and `Fast food (Y/N)`.
* Missing values are imputed (median) **inside** the cross-validated pipeline,
  together with standard scaling, so no test information leaks into training.

## EDA highlights

* Target is imbalanced: 364 no-PCOS vs 177 PCOS (2.06 : 1) - splits are stratified.
* Strongest correlates of PCOS: follicle counts (R = +0.65, L = +0.60), skin
  darkening, hair growth, weight gain, irregular cycles, fast food, AMH.
* A few physiologically impossible readings (e.g. `Pulse rate = 13`,
  `BP systolic = 12`) are flagged; scaling limits their impact on KNN distances.

## Model

Cross-validated accuracy on the training set:

| Model | CV accuracy |
|-------|-------------|
| Random Forest | 89.8% |
| SVM (RBF) | 88.4% |
| Logistic Regression | 86.8% |
| **KNN (tuned)** | **87.5%** |
| Gaussian NB | 79.4% |

**Chosen model: K-Nearest-Neighbours** (`n_neighbors=11`, `weights='uniform'`,
`p=1` / Manhattan), selected by `GridSearchCV`.

Held-out test set (109 patients):

| Metric | Value |
|--------|-------|
| **Accuracy** | **88.99%** |
| Precision | 96.2% |
| Recall | 69.4% |
| F1 | 80.6% |
| ROC-AUC | 0.924 |

Random Forest scores ~1 pt higher on CV; KNN is used as the project's model per
requirement and is competitive with a far simpler decision rule.
