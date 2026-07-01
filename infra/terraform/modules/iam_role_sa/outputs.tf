output "ml_workflow_role_arn" {
  value = aws_iam_role.ml_workflow.arn
}

output "mlflow_role_arn" {
  value = aws_iam_role.mlflow.arn
}

output "aily_api_role_arn" {
  value = aws_iam_role.aily_api.arn
}
