resource "aws_ecs_cluster" "app" {
  name = var.project

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_iam_role" "execution" {
  name = "${var.project}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_ssm" {
  name = "${var.project}-ecs-execution-ssm"
  role = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["ssm:GetParameters"]
      Resource = concat([
        aws_ssm_parameter.postgres_password.arn,
        aws_ssm_parameter.whatsapp_biz_access_token.arn,
        aws_ssm_parameter.whatsapp_biz_verify_token.arn,
        aws_ssm_parameter.whatsapp_test_access_token.arn,
        aws_ssm_parameter.whatsapp_test_verify_token.arn,
        aws_ssm_parameter.openai_api_key.arn,
        aws_ssm_parameter.jwt_secret.arn,
      ], var.internal_service_token_ssm_arn == "" ? [] : [var.internal_service_token_ssm_arn])
    }]
  })
}

resource "aws_iam_role" "task" {
  name = "${var.project}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

locals {
  server_image = "${aws_ecr_repository.server.repository_url}:latest"
  client_image = "${aws_ecr_repository.client.repository_url}:latest"

  common_environment = [
    { name = "ENVIRONMENT", value = "production" },
    { name = "LOG_LEVEL", value = "INFO" },
    { name = "POSTGRES_USER", value = var.postgres_user },
    { name = "POSTGRES_DB", value = var.postgres_db },
    { name = "INTERNAL_BUSINESS_ID", value = var.internal_business_id },
    { name = "POSTGRES_HOST", value = aws_db_instance.app.address },
    { name = "POSTGRES_PORT", value = tostring(aws_db_instance.app.port) },
    { name = "CORS_ORIGINS", value = var.cors_origins },
    { name = "WHATSAPP_BIZ_PHONE_NUMBER_ID", value = var.whatsapp_biz_phone_number_id },
    { name = "WHATSAPP_TEST_PHONE_NUMBER_ID", value = var.whatsapp_test_phone_number_id },
    { name = "ADMIN_WHATSAPP_NUMBERS", value = var.admin_whatsapp_numbers },
    { name = "WHATSAPP_PHONE_NUMBER_BUSINESS_IDS", value = var.whatsapp_phone_number_business_ids },
  ]

  common_secrets = concat([
    { name = "POSTGRES_PASSWORD", valueFrom = aws_ssm_parameter.postgres_password.arn },
    { name = "WHATSAPP_BIZ_ACCESS_TOKEN", valueFrom = aws_ssm_parameter.whatsapp_biz_access_token.arn },
    { name = "WHATSAPP_BIZ_VERIFY_TOKEN", valueFrom = aws_ssm_parameter.whatsapp_biz_verify_token.arn },
    { name = "WHATSAPP_TEST_ACCESS_TOKEN", valueFrom = aws_ssm_parameter.whatsapp_test_access_token.arn },
    { name = "WHATSAPP_TEST_VERIFY_TOKEN", valueFrom = aws_ssm_parameter.whatsapp_test_verify_token.arn },
    { name = "OPENAI_API_KEY", valueFrom = aws_ssm_parameter.openai_api_key.arn },
    { name = "JWT_SECRET", valueFrom = aws_ssm_parameter.jwt_secret.arn },
    ], var.internal_service_token_ssm_arn == "" ? [] : [{
      name      = "INTERNAL_SERVICE_TOKEN"
      valueFrom = var.internal_service_token_ssm_arn
  }])
}

resource "aws_ecs_task_definition" "server" {
  family                   = "${var.project}-server"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "server"
    image     = local.server_image
    essential = true
    portMappings = [{
      containerPort = var.container_port
      protocol      = "tcp"
    }]
    environment = local.common_environment
    secrets     = local.common_secrets
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.server.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "server"
      }
    }
  }])
}

# One-off migration task. CI/CD runs this via `aws ecs run-task` before
# updating the service, same role docker-compose's `migrate` service played locally.
resource "aws_ecs_task_definition" "migrate" {
  family                   = "${var.project}-migrate"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name        = "migrate"
    image       = local.server_image
    essential   = true
    command     = ["alembic", "upgrade", "head"]
    environment = local.common_environment
    secrets     = local.common_secrets
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.migrate.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "migrate"
      }
    }
  }])
}

resource "aws_ecs_service" "server" {
  name            = "${var.project}-server"
  cluster         = aws_ecs_cluster.app.id
  task_definition = aws_ecs_task_definition.server.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = local.multi_az_subnet_ids
    security_groups  = [aws_security_group.ecs_service.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "server"
    container_port   = var.container_port
  }

  depends_on = [aws_lb_listener.http]
}

# Owner dashboard / agent-office. NEXT_PUBLIC_* values are baked in at image
# build time (see client/Dockerfile ARG), not set here as runtime env vars.
resource "aws_ecs_task_definition" "client" {
  family                   = "${var.project}-client"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "client"
    image     = local.client_image
    essential = true
    portMappings = [{
      containerPort = var.client_container_port
      protocol      = "tcp"
    }]
    environment = [
      { name = "PORT", value = tostring(var.client_container_port) },
      { name = "HOSTNAME", value = "0.0.0.0" },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.client.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "client"
      }
    }
  }])
}

resource "aws_ecs_service" "client" {
  name            = "${var.project}-client"
  cluster         = aws_ecs_cluster.app.id
  task_definition = aws_ecs_task_definition.client.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = local.multi_az_subnet_ids
    security_groups  = [aws_security_group.ecs_service.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.client.arn
    container_name   = "client"
    container_port   = var.client_container_port
  }

  depends_on = [aws_lb_listener_rule.client]
}
