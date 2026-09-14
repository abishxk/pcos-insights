# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See `README.md` for the full write-up of the data, EDA and model results.

## What this is

PCOS (Polycystic Ovary Syndrome) prediction from `PCOS_data_without_infertility.xlsx`
(541 patients, sheet `Full_new`). Two things live here:

1. **Analysis pipeline** (`PCOS.py` + `pcos/`) - EDA and full-feature model
   comparison, producing `figures/*.png`.
2. **Flask web app** (`app.py` + `templates/` + `static/`) - a landing page and a
   symptom-only self-check questionnaire backed by a smaller KNN trained on 13
   user-answerable inputs.

## Commands

```bash
pip install -r requirements.txt

python PCOS.py                 # full pipeline (EDA + modelling)
python PCOS.py --no-eda        # modelling only
python -m pcos.eda             # EDA only
python -m pcos.model           # full-feature model comparison only

python -m pcos.symptom_model   # train + save the web app's symptom model
python app.py                  # serve on http://127.0.0.1:5000 (debug=True)
```

No test suite, no linter config, no build step. Windows environment; primary
shell is PowerShell. Not a git repository.

## Python architecture

| Path | Role |
|------|------|
| `pcos/data.py` | Single source of loading + cleaning. `load_clean_data()` returns numeric columns with `NaN` left in place. |
| `pcos/eda.py` | `run_eda()` - prints summary, writes `figures/01`-`06`. |
| `pcos/model.py` | `run()` - 5-fold stratified CV across 5 classifiers, `GridSearchCV` KNN tuning, held-out test eval, writes `figures/07`. |
| `pcos/symptom_model.py` | `train_and_save()` - trains the web KNN, writes `models/pcos_symptom_knn.joblib` (fitted `Pipeline`) + `models/pcos_symptom_meta.json`. |
| `app.py` | Routes: `GET /` landing, `GET /app` questionnaire, `POST /api/predict` JSON. Auto-trains the model on startup if the `models/` files are missing. |

`app.py` reads `models/pcos_symptom_meta.json` at import time and derives
everything downstream from it: `FIELD_TO_COLUMN`, the `/api/predict` feature
order, and the `meta` / `signals` / `base_rate` context passed to
`templates/index.html`. **If you change `FIELDS` in `pcos/symptom_model.py`,
retrain** or the meta file, the API and the front end fall out of sync.

## Front-end architecture

Hand-authored HTML/CSS/JS, no build step. Two pages that share a visual
language (video background, white nav pill, dot-matrix display face) but keep
**separate stylesheets with their own `:root` token blocks**:

| Page | Files |
|------|-------|
| `/` landing | `templates/landing.html`, `static/landing.css`, `static/landing.js` |
| `/app` tool | `templates/index.html`, `static/style.css`, `static/app.js` |

`static/landing.js` is loaded on **both** pages (it owns the burger menu,
overlay and background-video autoplay). Its stat count-up code is guarded and
no-ops when `.stat-value` is absent, which is how it survives on `/app`.

### `/app` is a two-view single-page flow

One `.card` holds two `<section class="view">` siblings toggled by the `hidden`
attribute, plus two native `<dialog class="modal">` elements outside the shell:

- `#formView` - questionnaire. `#openAbout` opens `#aboutModal` (the data/model
  explainer built from `meta` + `signals`).
- `#resultView` - the estimate. `#openOutputAbout` opens `#outputModal` (what
  the read-out means); `#restart` calls `showForm()` to reset and go back.
- `showResult()` / `showForm()` in `static/app.js` do the swap and toggle
  `card.classList` `result-mode`, which widens the card and turns the result
  grid two-column.

`render(data)` builds the whole result as an HTML string: a full-width `.hero`
(number, badge, meter, interpretation) spanning both columns, then `.col-a`
(how that compares, what to do next) and `.col-b` (what you reported, BMI).
Rebalance by moving blocks between `colA` / `colB`, not by adding columns.

### Layout mechanics that bite

- **`.view[hidden]` needs an explicit rule.** `.view { display: flex }` beats
  the UA `[hidden]` rule, so `style.css` carries `.view[hidden] { display: none }`.
  Same trap applies to any new element that sets `display` and is toggled by
  `hidden`.
- **`--cap-h` is set from JS.** `syncCapHeight()` measures `.app` and writes an
  absolute px value onto `:root`. The CSS fallback `calc(100dvh - 132px)` is
  only a first paint. This exists because `max-height: 100%` does not resolve
  against a parent that has only `max-height`, which silently clips content
  instead of scrolling it. Call `syncCapHeight()` after anything that changes
  content height.
- The whole page is designed to fit one viewport without scrolling. Adding
  vertical content to `/app` usually means removing some elsewhere.

### Motion and design conventions

`.agents/skills/` holds two skills that govern front-end work here
(`design-taste-frontend`, pinned in `skills-lock.json`, and `animate`). They are
not registered with the Skill tool - read the `SKILL.md` files directly. What
the existing code already follows:

- Animate `transform` / `opacity` only; the meter and signal bars use
  `scaleX()`, never `width`.
- Every transition and keyframe lives inside
  `@media (prefers-reduced-motion: no-preference)`; hover transforms live inside
  `@media (hover: hover) and (pointer: fine)`.
- Entrance stagger is `.anim` + `style="--i:N"` (delay `N * 60ms + 150ms`).
- **No em-dashes or en-dashes anywhere in user-visible copy.** Use ASCII
  hyphens, `%`, or `\2212`.

### Front-end details worth knowing

- The submit button doubles as a **progress bar**: `updateProgress()` writes a
  `--progress` custom property that drives `.submit-fill`'s `scaleX`, and adds
  `is-ready` at 100%. The label uses `mix-blend-mode: difference` so it stays
  legible over both the dark track and the white fill - do not replace the
  button's inner spans without preserving that structure.
- Busy state toggles `is-busy` and swaps `.submit-label` text; it must not
  `innerHTML`-replace the button (that would destroy `.submit-fill`).

## Non-obvious things

- **Sheet selection matters.** `pd.read_excel` defaults to the `Instructions`
  sheet (a read-me). Always go through `pcos/data.py`, which forces `Full_new`.
- **Two malformed cells** force `II beta-HCG(mIU/mL)` and `AMH(ng/mL)` to import
  as text (`"1.99."`, `"a"`); `load_clean_data` coerces them to numeric.
- **No imputation outside a pipeline.** Median imputation + `StandardScaler` sit
  *inside* the CV pipeline so no test information leaks. Keep it that way.
- **KNN is a project requirement**, not the top scorer - Random Forest beats it
  by ~1pt on CV. Don't "improve" the model by switching algorithms.
- The shipped symptom model is refit on **all 541 rows** after metrics are
  computed on a held-out split; the reported numbers come from the split.
- `/api/predict` clamps the displayed probability to [0.01, 0.99] (KNN vote
  share can be exactly 0/1) but returns the raw value in `probability`.
- `Cycle(R/I)` is encoded 2 = regular, 4 = irregular in the payload parser.
- `Reg.Exercise(Y/N)` is deliberately excluded from `FACTOR_LABELS`, so it is
  absent from both the app's "contributing factors" and the "strongest signals"
  panel - it trends mildly protective in the data.
- `static/assets/logo.webp` is a generated placeholder and
  `static/fonts/GeistPixel-Circle.woff2` is missing on purpose (see
  `static/fonts/README.txt`); both degrade gracefully.
