"""The BigQuery loader, with the Google clients mocked out."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from taxi_elt.config import Settings
from taxi_elt.load import load_bigquery

bigquery = pytest.importorskip("google.cloud.bigquery")


@pytest.fixture
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path,
        duckdb_path=tmp_path / "w.duckdb",
        gcp_project="demo-project",
        gcs_bucket="demo-lake",
        bq_raw_dataset="raw",
        bq_location="US",
        tlc_base_url="http://unused",
    )


def test_bigquery_load_uploads_then_swaps_month_in_one_transaction(settings):
    bq_client = mock.MagicMock()
    bq_client.get_table.return_value.schema = [
        SimpleNamespace(name="VendorID"),
        SimpleNamespace(name="fare_amount"),
    ]
    bq_client.query.return_value.result.return_value = iter([SimpleNamespace(n=123)])
    gcs_client = mock.MagicMock()

    with (
        mock.patch.object(bigquery, "Client", return_value=bq_client),
        mock.patch("google.cloud.storage.Client", return_value=gcs_client),
    ):
        rows = load_bigquery(Path("/tmp/yellow_tripdata_2024-01.parquet"), date(2024, 1, 1), settings)

    assert rows == 123
    gcs_client.bucket.assert_called_once_with("demo-lake")
    gcs_client.bucket().blob.assert_called_once_with(
        "raw/yellow_tripdata/month=2024-01/yellow_tripdata_2024-01.parquet"
    )
    uri, landing = bq_client.load_table_from_uri.call_args.args
    assert uri == "gs://demo-lake/raw/yellow_tripdata/month=2024-01/yellow_tripdata_2024-01.parquet"
    assert landing == "demo-project.raw._landing_yellow_trips_202401"

    script = next(c.args[0] for c in bq_client.query.call_args_list if "BEGIN TRANSACTION" in c.args[0])
    assert script.index("DELETE FROM") < script.index("INSERT INTO") < script.index("COMMIT TRANSACTION")
    assert "CAST(vendorid AS INT64) AS vendorid" in script
    assert "CAST(NULL AS FLOAT64) AS airport_fee" in script


def test_bigquery_load_requires_gcp_settings(settings):
    incomplete = Settings(**{**settings.__dict__, "gcs_bucket": None})
    with pytest.raises(RuntimeError, match="GCS_BUCKET"):
        load_bigquery(Path("x.parquet"), date(2024, 1, 1), incomplete)
