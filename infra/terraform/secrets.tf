# Credentials go through SSM Parameter Store (SecureString), not plaintext
# environment vars, so they don't show up in `ecs describe-task-definition`.

resource "aws_ssm_parameter" "postgres_password" {
  name  = "/${var.project}/postgres_password"
  type  = "SecureString"
  value = var.postgres_password
}

resource "aws_ssm_parameter" "whatsapp_biz_access_token" {
  name  = "/${var.project}/whatsapp_biz_access_token"
  type  = "SecureString"
  value = var.whatsapp_biz_access_token
}

resource "aws_ssm_parameter" "whatsapp_biz_verify_token" {
  name  = "/${var.project}/whatsapp_biz_verify_token"
  type  = "SecureString"
  value = var.whatsapp_biz_verify_token
}

resource "aws_ssm_parameter" "whatsapp_test_access_token" {
  name  = "/${var.project}/whatsapp_test_access_token"
  type  = "SecureString"
  value = var.whatsapp_test_access_token == "" ? "unset" : var.whatsapp_test_access_token
}

resource "aws_ssm_parameter" "whatsapp_test_verify_token" {
  name  = "/${var.project}/whatsapp_test_verify_token"
  type  = "SecureString"
  value = var.whatsapp_test_verify_token == "" ? "unset" : var.whatsapp_test_verify_token
}
