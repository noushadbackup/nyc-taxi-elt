locals {
  bucket_name = coalesce(var.bucket_name, "${var.project_id}-nyc-taxi-lake")

  # raw: written by the Airflow load task. The rest are created and owned by dbt.
  datasets = {
    raw         = "Raw NYC TLC trip records, loaded by Airflow"
    staging     = "dbt staging and intermediate views"
    marts       = "dbt marts: facts, dimensions and reporting tables"
    reference   = "dbt seeds (taxi zones, payment types)"
    dq_failures = "Rows that failed dbt data tests (store_failures)"
    nyc_taxi    = "dbt default dataset"
  }

  pipeline_roles = [
    "roles/bigquery.jobUser",
  ]
}

resource "google_project_service" "apis" {
  for_each = toset([
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "billingbudgets.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# --- Data lake --------------------------------------------------------------

resource "google_storage_bucket" "lake" {
  name                        = local.bucket_name
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true

  lifecycle_rule {
    condition {
      age = var.raw_file_retention_days
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.apis]
}

# --- Warehouse --------------------------------------------------------------

resource "google_bigquery_dataset" "datasets" {
  for_each = local.datasets

  dataset_id                 = each.key
  description                = each.value
  location                   = var.bq_location
  delete_contents_on_destroy = true

  depends_on = [google_project_service.apis]
}

# --- Pipeline identity --------------------------------------------------------

resource "google_service_account" "pipeline" {
  account_id   = "nyc-taxi-pipeline"
  display_name = "NYC taxi ELT pipeline (Airflow + dbt)"

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "pipeline" {
  for_each = toset(local.pipeline_roles)
  project  = var.project_id
  role     = each.value
  member   = google_service_account.pipeline.member
}

# Least privilege: edit access to this project's datasets and bucket only.
resource "google_bigquery_dataset_iam_member" "pipeline_editor" {
  for_each   = google_bigquery_dataset.datasets
  dataset_id = each.value.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = google_service_account.pipeline.member
}

resource "google_storage_bucket_iam_member" "pipeline_objects" {
  bucket = google_storage_bucket.lake.name
  role   = "roles/storage.objectAdmin"
  member = google_service_account.pipeline.member
}

# --- Cost guardrail -----------------------------------------------------------

resource "google_billing_budget" "monthly" {
  count           = var.billing_account_id == null ? 0 : 1
  billing_account = var.billing_account_id
  display_name    = "nyc-taxi-elt monthly budget"

  budget_filter {
    projects = ["projects/${data.google_project.this.number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.monthly_budget_usd)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 1.0
  }
}

data "google_project" "this" {
  project_id = var.project_id
}
