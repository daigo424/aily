output "gha_role_arn" {
  value       = aws_iam_role.gha.arn
  description = "GitHub Actions が AssumeRole する ARN (QUANTIZE_GHA_ROLE_ARN に設定)"
}

output "instance_profile_name" {
  value       = aws_iam_instance_profile.ec2.name
  description = "EC2 インスタンスプロファイル名 (QUANTIZE_INSTANCE_PROFILE に設定)"
}
