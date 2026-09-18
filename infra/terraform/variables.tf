variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "project" {
  type    = string
  default = "stockaware"
}

variable "my_ip_cidr" {
  description = "Your public IP/32, allowed direct Postgres access for local admin/debugging."
  type        = string
}

variable "container_port" {
  type    = number
  default = 8000
}

variable "task_cpu" {
  type    = number
  default = 256
}

variable "task_memory" {
  type    = number
  default = 512
}

variable "desired_count" {
  description = "Number of running Fargate tasks. Keep at 1 for now."
  type        = number
  default     = 1
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_allocated_storage" {
  type    = number
  default = 20
}

variable "postgres_user" {
  type    = string
  default = "stockaware"
}

variable "postgres_password" {
  type      = string
  sensitive = true
}

variable "postgres_db" {
  type    = string
  default = "stockaware"
}

variable "internal_business_id" {
  description = "UUID of the single business authorized for the internal service token."
  type        = string
  default     = ""
}

variable "internal_service_token_ssm_arn" {
  description = "ARN of an externally managed SecureString holding the internal service token."
  type        = string
  default     = ""
}

variable "whatsapp_biz_phone_number_id" {
  type      = string
  sensitive = true
}

variable "whatsapp_biz_access_token" {
  type      = string
  sensitive = true
}

variable "whatsapp_biz_verify_token" {
  type      = string
  sensitive = true
}

variable "whatsapp_test_phone_number_id" {
  type      = string
  default   = ""
  sensitive = true
}

variable "whatsapp_test_access_token" {
  type      = string
  default   = ""
  sensitive = true
}

variable "whatsapp_test_verify_token" {
  type      = string
  default   = ""
  sensitive = true
}

variable "admin_whatsapp_numbers" {
  description = "Comma-separated wa_id values (no +) allowed to send admin commands."
  type        = string
  default     = ""
}

variable "cors_origins" {
  type    = string
  default = "[\"http://localhost:3000\"]"
}

variable "openai_api_key" {
  type      = string
  default   = ""
  sensitive = true
}
