resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
}
resource "aws_internet_gateway" "main" { vpc_id = aws_vpc.main.id }
resource "aws_subnet" "public" {
  for_each                = var.zones
  vpc_id                  = aws_vpc.main.id
  availability_zone       = each.value.name
  cidr_block              = each.value.public_cidr
  map_public_ip_on_launch = false
}
resource "aws_subnet" "private" {
  for_each                = var.zones
  vpc_id                  = aws_vpc.main.id
  availability_zone       = each.value.name
  cidr_block              = each.value.private_cidr
  map_public_ip_on_launch = false
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
}
resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}
# Private tasks intentionally have no internet route. Deployers must add reviewed VPC endpoints
# for ECR/Secrets/Logs/S3 (or controlled egress) before applying this reference.
resource "aws_security_group" "edge" {
  name_prefix = "${var.name}-edge-"
  vpc_id      = aws_vpc.main.id
}
resource "aws_security_group" "api" {
  name_prefix = "${var.name}-api-"
  vpc_id      = aws_vpc.main.id
}
resource "aws_security_group" "data" {
  name_prefix = "${var.name}-data-"
  vpc_id      = aws_vpc.main.id
}
resource "aws_vpc_security_group_ingress_rule" "https" {
  security_group_id = aws_security_group.edge.id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}
resource "aws_vpc_security_group_ingress_rule" "api" {
  security_group_id            = aws_security_group.api.id
  referenced_security_group_id = aws_security_group.edge.id
  ip_protocol                  = "tcp"
  from_port                    = var.container_port
  to_port                      = var.container_port
}
resource "aws_vpc_security_group_egress_rule" "edge_api" {
  security_group_id            = aws_security_group.edge.id
  referenced_security_group_id = aws_security_group.api.id
  ip_protocol                  = "tcp"
  from_port                    = var.container_port
  to_port                      = var.container_port
}
resource "aws_vpc_security_group_ingress_rule" "database" {
  security_group_id            = aws_security_group.data.id
  referenced_security_group_id = aws_security_group.api.id
  ip_protocol                  = "tcp"
  from_port                    = var.database_port
  to_port                      = var.database_port
}
resource "aws_vpc_security_group_ingress_rule" "redis" {
  security_group_id            = aws_security_group.data.id
  referenced_security_group_id = aws_security_group.api.id
  ip_protocol                  = "tcp"
  from_port                    = var.redis_port
  to_port                      = var.redis_port
}
resource "aws_vpc_security_group_egress_rule" "api_database" {
  security_group_id            = aws_security_group.api.id
  referenced_security_group_id = aws_security_group.data.id
  ip_protocol                  = "tcp"
  from_port                    = var.database_port
  to_port                      = var.database_port
}
resource "aws_vpc_security_group_egress_rule" "api_redis" {
  security_group_id            = aws_security_group.api.id
  referenced_security_group_id = aws_security_group.data.id
  ip_protocol                  = "tcp"
  from_port                    = var.redis_port
  to_port                      = var.redis_port
}
resource "aws_lb" "api" {
  name                       = var.name
  internal                   = false
  load_balancer_type         = "application"
  subnets                    = [for subnet in aws_subnet.public : subnet.id]
  security_groups            = [aws_security_group.edge.id]
  enable_deletion_protection = true
  drop_invalid_header_fields = true
}
resource "aws_lb_target_group" "api" {
  name        = var.name
  port        = var.container_port
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id
  health_check { path = var.health_path }
}
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}
resource "aws_cloudwatch_log_group" "api" {
  name              = "/${var.name}/api"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.log_kms_key_arn
}
resource "aws_ecs_cluster" "main" {
  name = var.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}
resource "aws_ecs_task_definition" "api" {
  family                   = var.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn
  container_definitions = jsonencode([{
    name         = "api", image = var.image, essential = true, readonlyRootFilesystem = true, user = "10001:10001",
    portMappings = [{ containerPort = var.container_port, protocol = "tcp" }],
    environment  = [for name, value in var.environment : { name = name, value = value }],
    secrets      = [for name, arn in var.secrets : { name = name, valueFrom = arn }],
    logConfiguration = { logDriver = "awslogs", options = {
      "awslogs-group" = aws_cloudwatch_log_group.api.name, "awslogs-region" = var.region, "awslogs-stream-prefix" = "api"
    } }
  }])
}
resource "aws_ecs_service" "api" {
  name            = var.name
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_replicas
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = [for subnet in aws_subnet.private : subnet.id]
    security_groups  = [aws_security_group.api.id]
    assign_public_ip = false
  }
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = var.container_port
  }
  depends_on = [aws_lb_listener.https]
}
resource "aws_db_subnet_group" "main" {
  name       = var.name
  subnet_ids = [for subnet in aws_subnet.private : subnet.id]
}
resource "aws_db_instance" "main" {
  identifier                  = var.name
  engine                      = "postgres"
  engine_version              = var.postgres_version
  instance_class              = var.database_class
  allocated_storage           = var.database_storage_gb
  db_name                     = var.database_name
  username                    = var.database_username
  manage_master_user_password = true
  port                        = var.database_port
  multi_az                    = true
  storage_encrypted           = true
  publicly_accessible         = false
  deletion_protection         = true
  skip_final_snapshot         = false
  final_snapshot_identifier   = "${var.name}-final"
  backup_retention_period     = var.database_backup_days
  db_subnet_group_name        = aws_db_subnet_group.main.name
  vpc_security_group_ids      = [aws_security_group.data.id]
  auto_minor_version_upgrade  = true
}
resource "aws_elasticache_subnet_group" "main" {
  name       = var.name
  subnet_ids = [for subnet in aws_subnet.private : subnet.id]
}
resource "aws_elasticache_replication_group" "main" {
  replication_group_id       = var.name
  description                = "Cell queue reference"
  engine                     = "redis"
  engine_version             = var.redis_version
  node_type                  = var.redis_node_type
  num_cache_clusters         = length(var.zones)
  port                       = var.redis_port
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.data.id]
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  automatic_failover_enabled = true
  multi_az_enabled           = true
  user_group_ids             = var.redis_user_group_ids
}
resource "aws_s3_bucket" "archives" { bucket = var.archive_bucket }
resource "aws_s3_bucket_public_access_block" "archives" {
  bucket                  = aws_s3_bucket.archives.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_versioning" "archives" {
  bucket = aws_s3_bucket.archives.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "archives" {
  bucket = aws_s3_bucket.archives.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}
resource "aws_s3_bucket_lifecycle_configuration" "archives" {
  bucket = aws_s3_bucket.archives.id
  rule {
    id     = "retention"
    status = "Enabled"
    filter { prefix = "" }
    expiration { days = var.archive_retention_days }
    noncurrent_version_expiration { noncurrent_days = var.archive_retention_days }
  }
}
