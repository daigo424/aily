locals {
  oidc_provider = replace(var.oidc_provider_url, "https://", "")
}

# -------------------------------------------------------
# ML Workflow IRSA
# -------------------------------------------------------
data "aws_iam_policy_document" "ml_workflow_assume" {
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
      values   = ["system:serviceaccount:argo:ml-workflow"]
    }
  }
}

resource "aws_iam_role" "ml_workflow" {
  name               = "${var.name_prefix}-ml-workflow-role"
  assume_role_policy = data.aws_iam_policy_document.ml_workflow_assume.json
}

data "aws_iam_policy_document" "ml_workflow_policy" {
  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:ListBucket",
      "s3:DeleteObject",
    ]
    resources = [
      var.ml_data_bucket_arn,
      "${var.ml_data_bucket_arn}/*",
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey",
    ]
    resources = [var.kms_key_arn]
  }
}

resource "aws_iam_role_policy" "ml_workflow" {
  name   = "${var.name_prefix}-ml-workflow-policy"
  role   = aws_iam_role.ml_workflow.id
  policy = data.aws_iam_policy_document.ml_workflow_policy.json
}

# -------------------------------------------------------
# 2. MLflow IRSA
# -------------------------------------------------------
data "aws_iam_policy_document" "mlflow_assume" {
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
      values   = ["system:serviceaccount:mlflow:mlflow"]
    }
  }
}

resource "aws_iam_role" "mlflow" {
  name               = "${var.name_prefix}-mlflow-role"
  assume_role_policy = data.aws_iam_policy_document.mlflow_assume.json
}

data "aws_iam_policy_document" "mlflow_policy" {
  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:ListBucket",
      "s3:DeleteObject",
    ]
    resources = [
      var.ml_data_bucket_arn,
      "${var.ml_data_bucket_arn}/*",
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey",
    ]
    resources = [var.kms_key_arn]
  }
}

resource "aws_iam_role_policy" "mlflow" {
  name   = "${var.name_prefix}-mlflow-policy"
  role   = aws_iam_role.mlflow.id
  policy = data.aws_iam_policy_document.mlflow_policy.json
}

# -------------------------------------------------------
# vLLM IRSA (S3 read for model weights)
# -------------------------------------------------------
data "aws_iam_policy_document" "vllm_assume" {
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
      values   = ["system:serviceaccount:aily-ml:vllm"]
    }
  }
}

resource "aws_iam_role" "vllm" {
  name               = "${var.name_prefix}-vllm-role"
  assume_role_policy = data.aws_iam_policy_document.vllm_assume.json
}

data "aws_iam_policy_document" "vllm_policy" {
  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      var.ml_data_bucket_arn,
      "${var.ml_data_bucket_arn}/*",
    ]
  }

  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [var.kms_key_arn]
  }
}

resource "aws_iam_role_policy" "vllm" {
  name   = "${var.name_prefix}-vllm-policy"
  role   = aws_iam_role.vllm.id
  policy = data.aws_iam_policy_document.vllm_policy.json
}

# -------------------------------------------------------
# aily-api IRSA
# -------------------------------------------------------
data "aws_iam_policy_document" "aily_api_assume" {
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
      values   = ["system:serviceaccount:aily:aily-api"]
    }
  }
}

resource "aws_iam_role" "aily_api" {
  name               = "${var.name_prefix}-aily-api-role"
  assume_role_policy = data.aws_iam_policy_document.aily_api_assume.json
}

data "aws_iam_policy_document" "aily_api_policy" {
  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      var.ml_data_bucket_arn,
      "${var.ml_data_bucket_arn}/*",
    ]
  }

  statement {
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${var.ml_data_bucket_arn}/ml_data/app/message_attachments/*"]
  }

  statement {
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey",
    ]
    resources = [var.kms_key_arn]
  }
}

resource "aws_iam_role_policy" "aily_api" {
  name   = "${var.name_prefix}-aily-api-policy"
  role   = aws_iam_role.aily_api.id
  policy = data.aws_iam_policy_document.aily_api_policy.json
}

# -------------------------------------------------------
# Langfuse IRSA (S3 media upload)
# -------------------------------------------------------
data "aws_iam_policy_document" "langfuse_assume" {
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
      values   = ["system:serviceaccount:langfuse:langfuse"]
    }
  }
}

resource "aws_iam_role" "langfuse" {
  name               = "${var.name_prefix}-langfuse-role"
  assume_role_policy = data.aws_iam_policy_document.langfuse_assume.json
}

data "aws_iam_policy_document" "langfuse_policy" {
  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      "${var.ml_data_bucket_arn}/langfuse/*",
      var.ml_data_bucket_arn,
    ]
  }

  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [var.kms_key_arn]
  }
}

resource "aws_iam_role_policy" "langfuse" {
  name   = "${var.name_prefix}-langfuse-policy"
  role   = aws_iam_role.langfuse.id
  policy = data.aws_iam_policy_document.langfuse_policy.json
}
