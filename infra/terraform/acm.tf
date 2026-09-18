variable "webhook_domain" {
  type    = string
  default = "stockaware.vaaani.co.in"
}

resource "aws_acm_certificate" "app" {
  domain_name       = var.webhook_domain
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

output "acm_validation_record" {
  value = {
    name  = tolist(aws_acm_certificate.app.domain_validation_options)[0].resource_record_name
    type  = tolist(aws_acm_certificate.app.domain_validation_options)[0].resource_record_type
    value = tolist(aws_acm_certificate.app.domain_validation_options)[0].resource_record_value
  }
}

# Waits for ACM to see the validation CNAME at vaaani.co.in's DNS provider.
# Apply this (and the HTTPS listener) only after that record is added.
resource "aws_acm_certificate_validation" "app" {
  certificate_arn = aws_acm_certificate.app.arn
}

output "webhook_dns_record" {
  description = "Add this CNAME at vaaani.co.in's DNS provider once the cert is issued."
  value = {
    name  = var.webhook_domain
    type  = "CNAME"
    value = aws_lb.app.dns_name
  }
}

# Second hostname, same ALB, for the owner dashboard / agent-office client.
resource "aws_acm_certificate" "client" {
  domain_name       = var.client_domain
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate_validation" "client" {
  certificate_arn = aws_acm_certificate.client.arn
}

output "client_acm_validation_record" {
  value = {
    name  = tolist(aws_acm_certificate.client.domain_validation_options)[0].resource_record_name
    type  = tolist(aws_acm_certificate.client.domain_validation_options)[0].resource_record_type
    value = tolist(aws_acm_certificate.client.domain_validation_options)[0].resource_record_value
  }
}

output "client_dns_record" {
  description = "Add this CNAME at vaaani.co.in's DNS provider once the cert is issued."
  value = {
    name  = var.client_domain
    type  = "CNAME"
    value = aws_lb.app.dns_name
  }
}
