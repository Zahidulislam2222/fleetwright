mock_provider "aws" {}

variables {
  name     = "fleetwright-test"
  region   = "us-east-1"
  vpc_cidr = "10.70.0.0/16"
  zones = {
    a = { name = "us-east-1a", public_cidr = "10.70.1.0/24", private_cidr = "10.70.11.0/24" }
    b = { name = "us-east-1b", public_cidr = "10.70.2.0/24", private_cidr = "10.70.12.0/24" }
  }
  certificate_arn        = "arn:aws:acm:us-east-1:123456789012:certificate/test"
  image                  = "example.test/fleetwright@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  container_port         = 8010
  health_path            = "/healthz"
  cpu                    = 512
  memory                 = 1024
  api_replicas           = 2
  execution_role_arn     = "arn:aws:iam::123456789012:role/test-execution"
  task_role_arn          = "arn:aws:iam::123456789012:role/test-task"
  secrets                = {}
  environment            = { FW_ENVIRONMENT = "test" }
  log_kms_key_arn        = "arn:aws:kms:us-east-1:123456789012:key/00000000-0000-0000-0000-000000000000"
  log_retention_days     = 30
  postgres_version       = "17"
  database_class         = "db.t4g.small"
  database_storage_gb    = 20
  database_name          = "fleetwright"
  database_username      = "fwadmin"
  database_backup_days   = 7
  database_port          = 5432
  redis_version          = "7.1"
  redis_node_type        = "cache.t4g.small"
  redis_port             = 6379
  redis_user_group_ids   = ["test-acl"]
  archive_bucket         = "fleetwright-test-archives-example"
  archive_retention_days = 30
}

run "private_multizone_plan" {
  command = plan
  assert {
    condition     = output.private_subnet_count == 2 && output.database_multi_az && output.redis_multi_az
    error_message = "Reference must retain private redundant data placement."
  }
  assert {
    condition     = alltrue([for subnet in aws_subnet.private : !subnet.map_public_ip_on_launch])
    error_message = "Private workloads may not receive public IPs."
  }
  assert {
    condition     = aws_db_instance.main.storage_encrypted && !aws_db_instance.main.publicly_accessible
    error_message = "Database encryption/private reachability required."
  }
  assert {
    condition     = aws_elasticache_replication_group.main.transit_encryption_enabled && aws_s3_bucket_public_access_block.archives.block_public_policy
    error_message = "Redis TLS and private archives required."
  }
}

run "reject_single_zone" {
  command = plan
  variables { zones = { a = { name = "us-east-1a", public_cidr = "10.70.1.0/24", private_cidr = "10.70.11.0/24" } } }
  expect_failures = [var.zones]
}

run "reject_mutable_image" {
  command = plan
  variables { image = "example.test/fleetwright:latest" }
  expect_failures = [var.image]
}
