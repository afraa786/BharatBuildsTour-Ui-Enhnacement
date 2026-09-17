data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# RDS and the ALB both require subnets in at least two AZs.
data "aws_subnet" "selected" {
  for_each = toset(data.aws_subnets.default.ids)
  id       = each.value
}

locals {
  subnet_ids_by_az = {
    for id, subnet in data.aws_subnet.selected : subnet.availability_zone => id...
  }
  # One subnet per AZ, at least two AZs.
  multi_az_subnet_ids = [for az, ids in local.subnet_ids_by_az : ids[0]]
}
