# -*- coding: utf-8 -*-
"""PCOS prediction - project entry point.

Runs the whole pipeline end to end:

    1. Exploratory data analysis  (prints a summary, writes figures/*.png)
    2. Model comparison + KNN tuning
    3. Prints the chosen model (KNN) and its held-out test accuracy

Run:  python PCOS.py            (EDA + modelling)
      python PCOS.py --no-eda   (modelling only)

The individual stages also run on their own:
    python -m pcos.eda
    python -m pcos.model

Original notebook:
    https://colab.research.google.com/drive/1jFglEBu-P8-N9zbB5uCc06zk49JAb7VM
"""

import argparse

from pcos.eda import run_eda
from pcos.model import run as run_modelling


def main() -> None:
    parser = argparse.ArgumentParser(description="PCOS prediction pipeline")
    parser.add_argument("--no-eda", action="store_true", help="skip the EDA stage")
    args = parser.parse_args()

    if not args.no_eda:
        run_eda()
        print()

    run_modelling()


if __name__ == "__main__":
    main()
