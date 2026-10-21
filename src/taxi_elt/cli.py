"""Run extract + load for one month outside Airflow.

python -m taxi_elt.cli --month 2024-01 --target duckdb
python -m taxi_elt.cli --month 2021-01 --target duckdb --file data/sample/yellow_tripdata_2021-01_sample.parquet
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from taxi_elt.config import Settings, parse_month
from taxi_elt.extract import download_month
from taxi_elt.load import LOADERS, load


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--month", required=True, help="Month to load, YYYY-MM")
    parser.add_argument("--target", choices=sorted(LOADERS), default=os.getenv("WAREHOUSE_TARGET", "duckdb"))
    parser.add_argument("--file", type=Path, help="Load this local parquet file instead of downloading")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    month = parse_month(args.month)
    path = args.file or download_month(month, settings)
    rows = load(args.target, path, month, settings)
    print(f"{month:%Y-%m}: {rows} rows loaded into {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
