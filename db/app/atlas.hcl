variable "db_host" {
    type    = string
    default = getenv("APP_DB_HOST")
}

variable "db_name" {
    type    = string
    default = getenv("APP_DB_NAME")
}

variable "db_username" {
    type    = string
    default = getenv("APP_DB_USERNAME")
}

variable "db_password" {
    type    = string
    default = getenv("APP_DB_PASSWORD")
}

variable "db_port" {
    type    = string
    default = getenv("APP_DB_PORT")
}

variable "db_sslmode" {
    type    = string
    default = getenv("APP_DB_SSLMODE")
}

variable "dev_db_host" {
    type    = string
    default = getenv("APP_ATLAS_DEV_DB_HOST")
}

variable "dev_db_name" {
    type    = string
    default = getenv("APP_ATLAS_DEV_DB_NAME")
}

variable "dev_db_username" {
    type    = string
    default = getenv("APP_ATLAS_DEV_DB_USERNAME")
}

variable "dev_db_password" {
    type    = string
    default = getenv("APP_ATLAS_DEV_DB_PASSWORD")
}

variable "dev_db_port" {
    type    = string
    default = getenv("APP_ATLAS_DEV_DB_PORT")
}

variable "dev_db_sslmode" {
    type    = string
    default = getenv("APP_ATLAS_DEV_DB_SSLMODE")
}

locals {
  url     = "postgres://${var.db_username}:${var.db_password}@${var.db_host}:${var.db_port}/${var.db_name}?sslmode=${var.db_sslmode}&search_path=public"
  dev_url = "postgres://${var.dev_db_username}:${var.dev_db_password}@${var.dev_db_host}:${var.dev_db_port}/${var.dev_db_name}?sslmode=${var.dev_db_sslmode}&search_path=public"

  test_url     = "postgres://${var.db_username}:${var.db_password}@${var.db_host}:${var.db_port}/${var.db_name}_test?sslmode=${var.db_sslmode}&search_path=public"
  test_dev_url = "postgres://${var.dev_db_username}:${var.dev_db_password}@${var.dev_db_host}:${var.dev_db_port}/${var.dev_db_name}_test?sslmode=${var.dev_db_sslmode}&search_path=public"
}

data "hcl_schema" "app" {
  paths = fileset("schema/**/*.hcl")
}

env "local" {
  url = local.url
  dev = local.dev_url
  src = data.hcl_schema.app.url
}

env "test" {
  url = local.test_url
  dev = local.test_dev_url
  src = data.hcl_schema.app.url
}

env "deploy" {
  url = local.url
  dev = local.dev_url
  src = data.hcl_schema.app.url
}