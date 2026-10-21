"""Shared settings for the extract/load steps.

Everything is read from environment variables so the same code runs inside
Airflow, from the CLI and in CI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

TLC_BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"

# Canonical raw schema. TLC files drift over the years (column casing,
# int vs double, columns added later), so every load is projected onto this
# list. Types are given per warehouse.
RAW_COLUMNS: list[tuple[str, str, str]] = [
    # (name, bigquery type, duckdb type)
    ("vendorid", "INT64", "BIGINT"),
    ("tpep_pickup_datetime", "DATETIME", "TIMESTAMP"),
    ("tpep_dropoff_datetime", "DATETIME", "TIMESTAMP"),
    ("passenger_count", "INT64", "BIGINT"),
    ("trip_distance", "FLOAT64", "DOUBLE"),
    ("ratecodeid", "INT64", "BIGINT"),
    ("store_and_fwd_flag", "STRING", "VARCHAR"),
    ("pulocationid", "INT64", "BIGINT"),
    ("dolocationid", "INT64", "BIGINT"),
    ("payment_type", "INT64", "BIGINT"),
    ("fare_amount", "FLOAT64", "DOUBLE"),
    ("extra", "FLOAT64", "DOUBLE"),
    ("mta_tax", "FLOAT64", "DOUBLE"),
    ("tip_amount", "FLOAT64", "DOUBLE"),
    ("tolls_amount", "FLOAT64", "DOUBLE"),
    ("improvement_surcharge", "FLOAT64", "DOUBLE"),
    ("total_amount", "FLOAT64", "DOUBLE"),
    ("congestion_surcharge", "FLOAT64", "DOUBLE"),
    ("airport_fee", "FLOAT64", "DOUBLE"),
]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    duckdb_path: Path
    gcp_project: str | None
    gcs_bucket: str | None
    bq_raw_dataset: str
    bq_location: str
    tlc_base_url: str

    @classmethod
    def from_env(cls) -> Settings:
        data_dir = Path(os.getenv("DATA_DIR", "data"))
        return cls(
            data_dir=data_dir,
            duckdb_path=Path(os.getenv("DUCKDB_PATH", str(data_dir / "warehouse.duckdb"))),
            gcp_project=os.getenv("GCP_PROJECT_ID"),
            gcs_bucket=os.getenv("GCS_BUCKET"),
            bq_raw_dataset=os.getenv("BQ_RAW_DATASET", "raw"),
            bq_location=os.getenv("BQ_LOCATION", "US"),
            tlc_base_url=os.getenv("TLC_BASE_URL", TLC_BASE_URL),
        )


def parse_month(value: str) -> date:
    """Accept '2024-01' or '2024-01-15' and return the first day of that month."""
    parts = value.split("-")
    if len(parts) < 2:
        raise ValueError(f"Expected YYYY-MM, got {value!r}")
    return date(int(parts[0]), int(parts[1]), 1)
