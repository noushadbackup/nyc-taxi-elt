"""Load one month of trips into the raw layer of the warehouse.

Both loaders follow the same idempotent pattern:

1. land the file in a temporary table, exactly as it is in the parquet file
2. in one transaction, delete that month from raw.yellow_trips and insert the
   temp table projected onto the canonical schema (see config.RAW_COLUMNS)

Re-running a month therefore replaces it instead of duplicating it.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from taxi_elt.config import RAW_COLUMNS, Settings

log = logging.getLogger(__name__)

RAW_TABLE = "yellow_trips"


def projection_sql(available: set[str], type_index: int) -> str:
    """SELECT list that maps whatever columns a file has onto the canonical schema.

    `available` holds the lower-cased column names present in the file. Columns
    the file lacks (e.g. airport_fee before 2022) become typed NULLs.
    """
    exprs = []
    for col in RAW_COLUMNS:
        name, sql_type = col[0], col[type_index]
        source = name if name in available else "NULL"
        exprs.append(f"CAST({source} AS {sql_type}) AS {name}")
    return ",\n    ".join(exprs)


def load_duckdb(path: Path, month: date, settings: Settings) -> int:
    import duckdb

    settings.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(settings.duckdb_path))
    try:
        cols = ",\n    ".join(f"{name} {ddb}" for name, _, ddb in RAW_COLUMNS)
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        con.execute(
            f"""CREATE TABLE IF NOT EXISTS raw.{RAW_TABLE} (
    {cols},
    source_month DATE,
    _source_file VARCHAR,
    _loaded_at TIMESTAMP
)"""
        )
        con.execute("CREATE OR REPLACE TEMP TABLE landing AS SELECT * FROM read_parquet(?)", [str(path)])
        available = {r[0].lower() for r in con.execute("DESCRIBE landing").fetchall()}

        con.execute("BEGIN TRANSACTION")
        con.execute(f"DELETE FROM raw.{RAW_TABLE} WHERE source_month = ?", [month])
        con.execute(
            f"""INSERT INTO raw.{RAW_TABLE}
SELECT
    {projection_sql(available, 2)},
    ?::DATE AS source_month,
    ? AS _source_file,
    current_timestamp AS _loaded_at
FROM landing""",
            [month, path.name],
        )
        con.execute("COMMIT")
        (rows,) = con.execute(
            f"SELECT count(*) FROM raw.{RAW_TABLE} WHERE source_month = ?", [month]
        ).fetchone()
    finally:
        con.close()
    log.info("Loaded %s rows for %s into DuckDB", rows, month)
    return rows


def load_bigquery(path: Path, month: date, settings: Settings) -> int:
    from google.cloud import bigquery, storage

    if not (settings.gcp_project and settings.gcs_bucket):
        raise RuntimeError("GCP_PROJECT_ID and GCS_BUCKET must be set for the BigQuery target")

    # 1. Upload to the data lake, partitioned Hive-style by month.
    blob_name = f"raw/yellow_tripdata/month={month:%Y-%m}/{path.name}"
    gcs = storage.Client(project=settings.gcp_project)
    gcs.bucket(settings.gcs_bucket).blob(blob_name).upload_from_filename(str(path), timeout=600)
    uri = f"gs://{settings.gcs_bucket}/{blob_name}"
    log.info("Uploaded %s", uri)

    bq = bigquery.Client(project=settings.gcp_project, location=settings.bq_location)
    dataset = f"{settings.gcp_project}.{settings.bq_raw_dataset}"
    landing = f"{dataset}._landing_{RAW_TABLE}_{month:%Y%m}"
    target = f"{dataset}.{RAW_TABLE}"

    # 2. Land the file as-is in a short-lived table.
    job = bq.load_table_from_uri(
        uri,
        landing,
        job_config=bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        ),
    )
    job.result()
    bq.query(
        f"ALTER TABLE `{landing}` SET OPTIONS (expiration_timestamp = "
        "TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 1 DAY))"
    ).result()
    available = {f.name.lower() for f in bq.get_table(landing).schema}

    # 3. Swap the month into the partitioned raw table atomically.
    cols = ",\n    ".join(f"{name} {bq_type}" for name, bq_type, _ in RAW_COLUMNS)
    script = f"""
CREATE TABLE IF NOT EXISTS `{target}` (
    {cols},
    source_month DATE,
    _source_file STRING,
    _loaded_at TIMESTAMP
)
PARTITION BY DATE_TRUNC(source_month, MONTH)
OPTIONS (description = 'NYC TLC yellow taxi trips, one partition per source file');

BEGIN TRANSACTION;
DELETE FROM `{target}` WHERE source_month = @month;
INSERT INTO `{target}`
SELECT
    {projection_sql(available, 1)},
    @month AS source_month,
    @source_file AS _source_file,
    CURRENT_TIMESTAMP() AS _loaded_at
FROM `{landing}`;
COMMIT TRANSACTION;

DROP TABLE `{landing}`;
"""
    bq.query(
        script,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("month", "DATE", month),
                bigquery.ScalarQueryParameter("source_file", "STRING", uri),
            ]
        ),
    ).result()

    rows = next(
        iter(
            bq.query(
                f"SELECT count(*) AS n FROM `{target}` WHERE source_month = @month",
                job_config=bigquery.QueryJobConfig(
                    query_parameters=[bigquery.ScalarQueryParameter("month", "DATE", month)]
                ),
            ).result()
        )
    ).n
    log.info("Loaded %s rows for %s into BigQuery", rows, month)
    return rows


LOADERS = {"duckdb": load_duckdb, "bigquery": load_bigquery}


def load(target: str, path: Path, month: date, settings: Settings) -> int:
    try:
        loader = LOADERS[target]
    except KeyError:
        raise ValueError(f"Unknown target {target!r}, expected one of {sorted(LOADERS)}") from None
    return loader(path, month, settings)
