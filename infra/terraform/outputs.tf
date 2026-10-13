output "private_subnet_count" { value = length(aws_subnet.private) }
output "database_multi_az" { value = aws_db_instance.main.multi_az }
output "redis_multi_az" { value = aws_elasticache_replication_group.main.multi_az_enabled }
output "api_replicas" { value = aws_ecs_service.api.desired_count }
