variable "project_id" {
  description = "GCP project that will hold the bucket, datasets and service account."
  type        = string
}

variable "region" {
  description = "Region for the GCS bucket."
  type        = string
  default     = "us-central1"
}

variable "bq_location" {
  description = "BigQuery location. Must be compatible with the bucket region (US covers us-central1)."
  type        = string
  default     = "US"
}

variable "bucket_name" {
  description = "Data lake bucket name. Defaults to <project_id>-nyc-taxi-lake."
  type        = string
  default     = null
}

variable "raw_file_retention_days" {
  description = "Delete landed parquet files after this many days (they can always be re-downloaded)."
  type        = number
  default     = 90
}

variable "billing_account_id" {
  description = "Billing account for the budget alert. Leave null to skip the budget."
  type        = string
  default     = null
}

variable "monthly_budget_usd" {
  description = "Budget alert threshold in USD."
  type        = number
  default     = 5
}
