"""Download the REES46 multi-category store dataset from Kaggle.

Dataset: "eCommerce behavior data from multi category store" by Michael Kechinov / REES46
https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store

The two files this project uses (Oct + Nov 2019) are ~14 GB uncompressed together.

Option A - Kaggle API (recommended)
    1. pip install kaggle
    2. Kaggle -> Settings -> API -> "Create New Token" -> save kaggle.json to
       ~/.kaggle/kaggle.json  (Windows: C:\\Users\\<you>\\.kaggle\\kaggle.json)
    3. python scripts/download_data.py

Option B - manual
    Download 2019-Oct.csv and 2019-Nov.csv from the Kaggle page and put them in data/raw/.
"""
from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DATASET = "mkechinov/ecommerce-behavior-data-from-multi-category-store"
FILES = ["2019-Oct.csv", "2019-Nov.csv"]


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        if (RAW / f).exists():
            print(f"already have {f}")
            continue
        print(f"downloading {f} (large - this takes a while)...")
        cmd = [sys.executable, "-m", "kaggle", "datasets", "download", "-d", DATASET, "-f", f, "-p", str(RAW)]
        if subprocess.run(cmd).returncode != 0:
            sys.exit("Kaggle download failed. Check ~/.kaggle/kaggle.json, or download manually (see this file's docstring).")
        z = RAW / f"{f}.zip"
        if z.exists():
            with zipfile.ZipFile(z) as zf:
                zf.extractall(RAW)
            z.unlink()
    print("Done. Next: python scripts/run_pipeline.py")


if __name__ == "__main__":
    main()
