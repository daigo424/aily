output "lbc_role_arn" {
  value = aws_iam_role.lbc.arn
}

output "argo_workflows_server_role_arn" {
  value = aws_iam_role.argo_workflows_server.arn
}
