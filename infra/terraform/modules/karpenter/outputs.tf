output "role_arn" {
  value = aws_iam_role.karpenter.arn
}

output "queue_name" {
  value = aws_sqs_queue.karpenter.name
}
