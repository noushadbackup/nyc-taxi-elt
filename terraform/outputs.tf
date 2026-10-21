output "bucket_name" {
  value = google_storage_bucket.lake.name
}

output "service_account_email" {
  value = google_service_account.pipeline.email
}

output "env_file_snippet" {
  description = "Paste into .env to point the pipeline at BigQuery."
  value       = <<-EOT
    WAREHOUSE_TARGET=bigquery
    DBT_TARGET=bigquery
    GCP_PROJECT_ID=${var.project_id}
    GCS_BUCKET=${google_storage_bucket.lake.name}
    BQ_LOCATION=${var.bq_location}
    GOOGLE_APPLICATION_CREDENTIALS=/opt/airflow/secrets/gcp-key.json
  EOT
}
