terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Local state for now. Once the team is on this, move to an S3 backend
  # (with a DynamoDB lock table) so state isn't stuck on one laptop.
}

provider "aws" {
  region = var.aws_region
}
