resource "aws_cloudwatch_log_group" "server" {
  name              = "/ecs/${var.project}-server"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "migrate" {
  name              = "/ecs/${var.project}-migrate"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "client" {
  name              = "/ecs/${var.project}-client"
  retention_in_days = 14
}
