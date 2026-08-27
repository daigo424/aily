# 手動スナップショット一覧を取得（存在しない場合は空リストになりエラーにならない）
data "aws_db_snapshots" "restore" {
  db_instance_identifier = var.name_prefix
  snapshot_type          = "manual"
}

locals {
  # snapshot_create_time の辞書順ソートで最新を取得（ISO8601 は辞書順 = 時系列）
  _sorted = sort([
    for s in data.aws_db_snapshots.restore.snapshots : "${s.snapshot_create_time}###${s.db_snapshot_arn}"
  ])
  latest_snapshot_arn = length(local._sorted) > 0 ? split("###", reverse(local._sorted)[0])[1] : null
}

# DB 削除時に同名の既存 final snapshot を削除して新しいスナップショットを作れるようにする
resource "terraform_data" "snapshot_cleanup" {
  input = "${var.name_prefix}-final"

  provisioner "local-exec" {
    when    = destroy
    command = "aws rds delete-db-snapshot --db-snapshot-identifier ${self.output} 2>/dev/null || true"
  }

  depends_on = [aws_db_instance.ml_db]
}

resource "aws_db_subnet_group" "ml_db" {
  name       = var.name_prefix
  subnet_ids = var.private_subnet_ids

  tags = {
    Name = "${var.name_prefix}-subnet-group"
  }
}

resource "aws_security_group" "ml_db" {
  name        = "${var.name_prefix}-rds-sg"
  description = "Security group for RDS"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  dynamic "ingress" {
    for_each = length(var.allowed_cidrs) > 0 ? [1] : []
    content {
      from_port   = 5432
      to_port     = 5432
      protocol    = "tcp"
      cidr_blocks = var.allowed_cidrs
      description = "Additional access for local development"
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name_prefix}-rds-sg"
  }
}

resource "aws_db_instance" "ml_db" {
  identifier            = var.name_prefix
  engine                = "postgres"
  engine_version        = "16"
  instance_class        = "db.t3.micro"
  allocated_storage     = 20
  max_allocated_storage = 100

  db_name  = "app"
  username = var.db_username
  password = "dummydummydummydummy"

  db_subnet_group_name   = aws_db_subnet_group.ml_db.name
  vpc_security_group_ids = [aws_security_group.ml_db.id]

  multi_az            = false
  publicly_accessible = true
  apply_immediately   = true

  backup_retention_period   = 1
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.name_prefix}-final"
  deletion_protection       = false

  snapshot_identifier = local.latest_snapshot_arn

  tags = {
    Name = var.name_prefix
  }

  lifecycle {
    ignore_changes = [password, snapshot_identifier]
  }
}
