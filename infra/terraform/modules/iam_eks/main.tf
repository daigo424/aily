locals {
  oidc_provider = replace(var.oidc_provider_url, "https://", "")
}

# -------------------------------------------------------
# AWS Load Balancer Controller IRSA
# -------------------------------------------------------
data "aws_iam_policy_document" "lbc_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider}:sub"
      values   = ["system:serviceaccount:kube-system:aws-load-balancer-controller"]
    }
  }
}

resource "aws_iam_role" "lbc" {
  name               = "${var.name_prefix}-lbc-role"
  assume_role_policy = data.aws_iam_policy_document.lbc_assume.json
}

resource "aws_iam_policy" "lbc" {
  name   = "${var.name_prefix}-lbc-policy"
  policy = file("${path.module}/policies/aws-lbc-policy.json")
}

resource "aws_iam_role_policy_attachment" "lbc" {
  role       = aws_iam_role.lbc.name
  policy_arn = aws_iam_policy.lbc.arn
}

# -------------------------------------------------------
# Argo Workflows Server IRSA
# -------------------------------------------------------
data "aws_iam_policy_document" "argo_workflows_server_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider}:sub"
      values   = ["system:serviceaccount:argo:argo-workflows-server"]
    }
  }
}

resource "aws_iam_role" "argo_workflows_server" {
  name               = "${var.name_prefix}-argo-workflows-server-role"
  assume_role_policy = data.aws_iam_policy_document.argo_workflows_server_assume.json
}

data "aws_iam_policy_document" "argo_workflows_server_policy" {
  statement {
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [var.ml_data_bucket_arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["logs/argo-workflows/*"]
    }
  }

  statement {
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${var.ml_data_bucket_arn}/logs/argo-workflows/*"]
  }

  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [var.kms_key_arn]
  }
}

resource "aws_iam_role_policy" "argo_workflows_server" {
  name   = "${var.name_prefix}-argo-workflows-server-policy"
  role   = aws_iam_role.argo_workflows_server.id
  policy = data.aws_iam_policy_document.argo_workflows_server_policy.json
}
