from datetime import date
from pathlib import Path

import duckdb
import pytest

from taxi_elt.config import RAW_COLUMNS, Settings, parse_month
from taxi_elt.load import load, projection_sql

SAMPLE = Path(__file__).parents[1] / "data/sample/yellow_tripdata_2021-01_sample.parquet"


@pytest.fixture
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path,
        duckdb_path=tmp_path / "warehouse.duckdb",
        gcp_project=None,
        gcs_bucket=None,
        bq_raw_dataset="raw",
        bq_location="US",
        tlc_base_url="http://unused",
    )


def test_parse_month():
    assert parse_month("2024-03") == date(2024, 3, 1)
    assert parse_month("2024-03-17") == date(2024, 3, 1)
    with pytest.raises(ValueError):
        parse_month("2024")


def test_projection_fills_missing_columns_with_typed_nulls():
    sql = projection_sql({"vendorid", "fare_amount"}, type_index=1)
    assert "CAST(vendorid AS INT64) AS vendorid" in sql
    assert "CAST(NULL AS FLOAT64) AS airport_fee" in sql
    assert sql.count(" AS ") == 2 * len(RAW_COLUMNS)


def test_duckdb_load_is_idempotent(settings):
    month = date(2021, 1, 1)
    first = load("duckdb", SAMPLE, month, settings)
    second = load("duckdb", SAMPLE, month, settings)

    con = duckdb.connect(str(settings.duckdb_path), read_only=True)
    total = con.execute("SELECT count(*) FROM raw.yellow_trips").fetchone()[0]
    assert first == second == total == 20_000


def test_duckdb_load_keeps_other_months(settings):
    load("duckdb", SAMPLE, date(2021, 1, 1), settings)
    load("duckdb", SAMPLE, date(2021, 2, 1), settings)
    load("duckdb", SAMPLE, date(2021, 1, 1), settings)

    con = duckdb.connect(str(settings.duckdb_path), read_only=True)
    rows = con.execute("SELECT source_month, count(*) FROM raw.yellow_trips GROUP BY 1 ORDER BY 1").fetchall()
    assert rows == [(date(2021, 1, 1), 20_000), (date(2021, 2, 1), 20_000)]


def test_unknown_target_is_rejected(settings):
    with pytest.raises(ValueError, match="Unknown target"):
        load("snowflake", SAMPLE, date(2021, 1, 1), settings)
