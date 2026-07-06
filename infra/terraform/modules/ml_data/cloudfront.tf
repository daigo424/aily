data "aws_caller_identity" "current" {}

# CloudFront Origin Access Control for S3 (OAC supports SSE-KMS, unlike legacy OAI)
resource "aws_cloudfront_origin_access_control" "ml_data" {
  name                              = "${var.name_prefix}-ml-data-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "ml_data" {
  origin {
    domain_name              = aws_s3_bucket.ml_data.bucket_regional_domain_name
    origin_id                = "ml-data-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.ml_data.id
  }

  enabled         = true
  comment         = "${var.name_prefix} message attachments"
  http_version    = "http2and3"
  is_ipv6_enabled = true

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "ml-data-s3"
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    # AWS managed CachingOptimized policy
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# S3 bucket policy: allow CloudFront OAC to read attachments prefix only
resource "aws_s3_bucket_policy" "ml_data_cloudfront" {
  bucket = aws_s3_bucket.ml_data.id
  policy = data.aws_iam_policy_document.ml_data_bucket_policy.json
}

data "aws_iam_policy_document" "ml_data_bucket_policy" {
  statement {
    sid    = "AllowCloudFrontOACReadAttachments"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.ml_data.arn}/ml_data/app/message_attachments/*"]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.ml_data.arn]
    }
  }
}

# KMS key policy: preserve root access + grant CloudFront Decrypt for SSE-KMS objects
resource "aws_kms_key_policy" "ml_data" {
  key_id = aws_kms_key.ml_data_key.id
  policy = data.aws_iam_policy_document.ml_data_kms_policy.json
}

data "aws_iam_policy_document" "ml_data_kms_policy" {
  statement {
    sid    = "EnableIAMUserPermissions"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
    actions   = ["kms:*"]
    resources = ["*"]
  }

  statement {
    sid    = "AllowCloudFrontOACDecrypt"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions   = ["kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.ml_data.arn]
    }
  }
}
