# ── EC2 インスタンスロール（SSM + S3書き込み）────────────────────────────────

resource "aws_iam_role" "ec2" {
  name = "${var.name_prefix}-quantize-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "ec2_s3" {
  statement {
    effect  = "Allow"
    actions = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
    resources = [
      var.ml_data_bucket_arn,
      "${var.ml_data_bucket_arn}/*",
    ]
  }

}

resource "aws_iam_role_policy" "ec2_s3" {
  name   = "S3MlDataWrite"
  role   = aws_iam_role.ec2.id
  policy = data.aws_iam_policy_document.ec2_s3.json
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${var.name_prefix}-quantize-instance-profile"
  role = aws_iam_role.ec2.name
}

# ── GitHub Actions ロール（OIDC）──────────────────────────────────────────────

data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

data "aws_iam_policy_document" "gha_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:*"]
    }
  }
}

resource "aws_iam_role" "gha" {
  name               = "${var.name_prefix}-quantize-gha-role"
  assume_role_policy = data.aws_iam_policy_document.gha_assume_role.json
}

data "aws_iam_policy_document" "gha" {
  # EC2 操作
  statement {
    effect = "Allow"
    actions = [
      "ec2:RunInstances",
      "ec2:TerminateInstances",
      "ec2:CreateSecurityGroup",
      "ec2:DeleteSecurityGroup",
      "ec2:DescribeInstances",
      "ec2:DescribeInstanceStatus",
      "ec2:DescribeImages",
      "ec2:DescribeSecurityGroups",
      "ec2:CreateTags",
    ]
    resources = ["*"]
  }

  # インスタンスプロファイル名の動的取得（ListInstanceProfiles はリソーススコープ不可）
  statement {
    effect    = "Allow"
    actions   = ["iam:ListInstanceProfiles"]
    resources = ["*"]
  }

  # EC2 インスタンスプロファイルの PassRole（quantize EC2 ロールのみ）
  statement {
    effect    = "Allow"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.ec2.arn]
  }

  # SSM コマンド送受信
  statement {
    effect = "Allow"
    actions = [
      "ssm:SendCommand",
      "ssm:GetCommandInvocation",
      "ssm:DescribeInstanceInformation",
    ]
    resources = ["*"]
  }

  # S3 バケット名の動的取得（ListAllMyBuckets はリソーススコープ不可）
  statement {
    effect    = "Allow"
    actions   = ["s3:ListAllMyBuckets"]
    resources = ["*"]
  }

  # S3 一時スクリプトの読み書き・削除
  statement {
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      var.ml_data_bucket_arn,
      "${var.ml_data_bucket_arn}/*",
    ]
  }

}

resource "aws_iam_role_policy" "gha" {
  name   = "QuantizeGhaPolicy"
  role   = aws_iam_role.gha.id
  policy = data.aws_iam_policy_document.gha.json
}
