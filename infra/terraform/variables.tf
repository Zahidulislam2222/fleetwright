variable "name" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,19}$", var.name))
    error_message = "Use a short lowercase resource prefix."
  }
}
variable "region" { type = string }
variable "vpc_cidr" { type = string }
variable "zones" {
  type = map(object({ name = string, public_cidr = string, private_cidr = string }))
  validation {
    condition     = length(var.zones) >= 2 && length(distinct([for zone in var.zones : zone.name])) == length(var.zones)
    error_message = "Reference requires at least two distinct availability zones."
  }
}
variable "certificate_arn" { type = string }
variable "image" {
  type = string
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.image))
    error_message = "Application image must be immutable and pinned by digest."
  }
}
variable "container_port" { type = number }
variable "health_path" { type = string }
variable "cpu" { type = number }
variable "memory" { type = number }
variable "api_replicas" {
  type = number
  validation {
    condition     = var.api_replicas >= 2
    error_message = "Reference requires at least two API replicas."
  }
}
variable "execution_role_arn" { type = string }
variable "task_role_arn" { type = string }
variable "secrets" {
  description = "Environment name to Secrets Manager or SSM ARN; never put secret values here."
  type        = map(string)
}
variable "environment" { type = map(string) }
variable "log_kms_key_arn" { type = string }
variable "log_retention_days" { type = number }
variable "postgres_version" { type = string }
variable "database_class" { type = string }
variable "database_storage_gb" { type = number }
variable "database_name" { type = string }
variable "database_username" { type = string }
variable "database_backup_days" { type = number }
variable "database_port" { type = number }
variable "redis_version" { type = string }
variable "redis_node_type" { type = string }
variable "redis_port" { type = number }
variable "redis_user_group_ids" {
  type = set(string)
  validation {
    condition     = length(var.redis_user_group_ids) > 0
    error_message = "Supply configured Redis ACL user group IDs; unauthenticated Redis is forbidden."
  }
}
variable "archive_bucket" { type = string }
variable "archive_retention_days" { type = number }
