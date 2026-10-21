.DEFAULT_GOAL := help
SHELL := /bin/bash

PYTHON ?= python3
VENV   := .venv
BIN    := $(VENV)/bin
DBT    := cd dbt && ../$(BIN)/dbt
SAMPLE := data/sample/yellow_tripdata_2021-01_sample.parquet
MONTH  ?= 2025-06

export PYTHONPATH := src
-include .env
export

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

init: ## Create .env and the local virtualenv
	@test -f .env || (cp .env.example .env && sed -i.bak "s/^AIRFLOW_UID=.*/AIRFLOW_UID=$$(id -u)/" .env && rm -f .env.bak)
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -q -r requirements-dev.txt

# --- Run without Airflow --------------------------------------------------------

sample: ## Load the bundled 20k-row sample into DuckDB and run dbt build
	$(BIN)/python -m taxi_elt.cli --target duckdb --month 2021-01 --file $(SAMPLE)
	$(DBT) build --profiles-dir . --target duckdb

# On the host, use the key in secrets/ rather than the container path from .env.
month: export GOOGLE_APPLICATION_CREDENTIALS := $(if $(wildcard secrets/gcp-key.json),$(CURDIR)/secrets/gcp-key.json,)
month: ## Download + load MONTH=YYYY-MM into WAREHOUSE_TARGET, then dbt build it
	$(BIN)/python -m taxi_elt.cli --target $(WAREHOUSE_TARGET) --month $(MONTH)
	$(DBT) build --profiles-dir . --target $(DBT_TARGET) --vars '{"month": "$(MONTH)-01"}'

docs: ## Generate and serve dbt docs (lineage graph) on :8081
	$(DBT) docs generate --profiles-dir . && $(DBT) docs serve --profiles-dir . --port 8081

test: ## Python unit tests + lint
	$(BIN)/pytest -q
	$(BIN)/ruff check src tests dags

# --- Airflow --------------------------------------------------------------------

up: ## Start Airflow (http://localhost:8080)
	docker compose up -d --build
	@echo "Airflow UI: http://localhost:8080 (unpause the nyc_taxi_elt DAG)"

down: ## Stop Airflow
	docker compose down

logs: ## Tail Airflow logs
	docker compose logs -f airflow

# --- GCP --------------------------------------------------------------------------

tf-apply: ## Create the GCS bucket, BigQuery datasets and service account
	cd terraform && terraform init -input=false && terraform apply

tf-key: ## Create a key for the pipeline service account in secrets/
	gcloud iam service-accounts keys create secrets/gcp-key.json \
	  --iam-account="$$(cd terraform && terraform output -raw service_account_email)"

tf-destroy: ## Delete everything Terraform created (data included)
	cd terraform && terraform destroy

clean: ## Remove local warehouse, downloads and dbt artifacts
	rm -rf data/landing data/warehouse.duckdb dbt/target dbt/logs

.PHONY: help init sample month docs test up down logs tf-apply tf-key tf-destroy clean
