"""NYC taxi ELT: TLC parquet -> (GCS ->) warehouse raw layer -> dbt models + tests.

One run per month of trip data. Each run waits for TLC to publish the file,
downloads it, loads it idempotently into raw.yellow_trips, then runs
`dbt build` (models + data tests) for that month only. Re-running or
backfilling a month replaces it, it never duplicates it.

Set WAREHOUSE_TARGET=bigquery (plus the GCP settings in .env) to load into
BigQuery; the default runs fully locally on DuckDB.
"""

from __future__ import annotations

import os
from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag, task
from airflow.timetables.interval import CronDataIntervalTimetable

TARGET = os.getenv("WAREHOUSE_TARGET", "duckdb")
START_MONTH = os.getenv("START_MONTH", "2025-06")
DBT_BIN = os.getenv("DBT_BIN", "dbt")
DBT_PROJECT_DIR = os.getenv("DBT_PROJECT_DIR", "/opt/airflow/dbt")

# The run for a month is created when that month ends; data_interval_start is
# the first day of the month being processed.
MONTH = "{{ data_interval_start | ds }}"


@dag(
    dag_id="nyc_taxi_elt",
    description="Monthly NYC yellow taxi trips -> raw -> dbt marts, with data quality tests",
    schedule=CronDataIntervalTimetable("0 0 1 * *", timezone="UTC"),
    start_date=pendulum.parse(f"{START_MONTH}-01", tz="UTC"),
    catchup=True,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["nyc-taxi", "elt", TARGET],
    doc_md=__doc__,
)
def nyc_taxi_elt():
    @task.sensor(poke_interval=timedelta(hours=12), timeout=timedelta(days=60), mode="reschedule")
    def wait_for_tlc_file(month: str) -> bool:
        """TLC publishes each month roughly two months late; check back twice a day."""
        import requests

        from taxi_elt.config import Settings, parse_month
        from taxi_elt.extract import file_name

        url = f"{Settings.from_env().tlc_base_url}/{file_name(parse_month(month))}"
        return requests.head(url, timeout=30).status_code == 200

    @task
    def extract(month: str) -> str:
        from taxi_elt.config import Settings, parse_month
        from taxi_elt.extract import download_month

        return str(download_month(parse_month(month), Settings.from_env()))

    @task
    def load(path: str, month: str) -> int:
        from pathlib import Path

        from taxi_elt.config import Settings, parse_month
        from taxi_elt.load import load as load_month

        return load_month(TARGET, Path(path), parse_month(month), Settings.from_env())

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"{DBT_BIN} build --profiles-dir . --target {TARGET} "
            f'--vars \'{{"month": "{MONTH}"}}\''
        ),
        # dbt writes to the warehouse; never run two months at once.
        max_active_tis_per_dag=1,
    )

    path = extract(MONTH)
    wait_for_tlc_file(MONTH) >> path
    load(path, MONTH) >> dbt_build


nyc_taxi_elt()
