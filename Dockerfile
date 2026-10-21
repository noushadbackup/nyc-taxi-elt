FROM apache/airflow:3.3.2-python3.12

COPY requirements-airflow.txt requirements-dbt.txt /tmp/

RUN pip install --no-cache-dir -r /tmp/requirements-airflow.txt \
 && python -m venv /home/airflow/dbt-venv \
 && /home/airflow/dbt-venv/bin/pip install --no-cache-dir -r /tmp/requirements-dbt.txt

ENV DBT_BIN=/home/airflow/dbt-venv/bin/dbt \
    PYTHONPATH=/opt/airflow/src
