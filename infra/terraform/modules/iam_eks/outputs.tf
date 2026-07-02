output "lbc_role_arn" {
  value = aws_iam_role.lbc.arn
}

output "argo_workflows_server_role_arn" {
  value = aws_iam_role.argo_workflows_server.arn
}

output "s3_csi_role_arn" {
  value = aws_iam_role.s3_csi.arn
}
