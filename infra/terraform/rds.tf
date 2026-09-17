resource "aws_db_subnet_group" "app" {
  name       = "${var.project}-db"
  subnet_ids = local.multi_az_subnet_ids
}

resource "aws_db_instance" "app" {
  identifier     = "${var.project}-db"
  engine         = "postgres"
  engine_version = "17"
  instance_class = var.db_instance_class

  allocated_storage = var.db_allocated_storage
  storage_type      = "gp3"

  db_name  = var.postgres_db
  username = var.postgres_user
  password = var.postgres_password

  db_subnet_group_name   = aws_db_subnet_group.app.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  multi_az                = false
  backup_retention_period = 1
  skip_final_snapshot     = true
  deletion_protection     = false
}
