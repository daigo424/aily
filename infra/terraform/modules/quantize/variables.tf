variable "name_prefix" {
  type = string
}

variable "github_repo" {
  type        = string
  description = "GitHub repo (例: daigo424/aily)"
}

variable "ml_data_bucket_arn" {
  type        = string
  description = "ml_data S3 バケットの ARN"
}

variable "kms_key_arn" {
  type        = string
  description = "ml_data バケットの KMS キー ARN"
}
