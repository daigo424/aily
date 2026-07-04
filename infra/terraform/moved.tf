# state を module.ml_data に移行する moved ブロック。
# terraform apply で state 移行が完了したら、このファイルは削除してよい。

moved {
  from = aws_kms_key.ml_data_key
  to   = module.ml_data.aws_kms_key.ml_data_key
}

moved {
  from = aws_s3_bucket.ml_data
  to   = module.ml_data.aws_s3_bucket.ml_data
}

moved {
  from = aws_s3_bucket_server_side_encryption_configuration.ml_data
  to   = module.ml_data.aws_s3_bucket_server_side_encryption_configuration.ml_data
}

moved {
  from = aws_s3_bucket_public_access_block.ml_data
  to   = module.ml_data.aws_s3_bucket_public_access_block.ml_data
}

moved {
  from = aws_s3_bucket_lifecycle_configuration.ml_data
  to   = module.ml_data.aws_s3_bucket_lifecycle_configuration.ml_data
}

moved {
  from = aws_s3_bucket.ml_data_log
  to   = module.ml_data.aws_s3_bucket.ml_data_log
}

moved {
  from = aws_s3_bucket_public_access_block.ml_data_log
  to   = module.ml_data.aws_s3_bucket_public_access_block.ml_data_log
}

moved {
  from = aws_s3_bucket_lifecycle_configuration.ml_data_log
  to   = module.ml_data.aws_s3_bucket_lifecycle_configuration.ml_data_log
}

moved {
  from = aws_s3_bucket_logging.ml_data
  to   = module.ml_data.aws_s3_bucket_logging.ml_data
}

moved {
  from = aws_iam_role.github_actions_role
  to   = module.ml_data.aws_iam_role.github_actions_role
}

moved {
  from = aws_iam_role_policy.github_actions_role_policy
  to   = module.ml_data.aws_iam_role_policy.github_actions_role_policy
}

moved {
  from = module.iam_eks[0].aws_iam_role.argo_workflows
  to   = module.iam_eks[0].aws_iam_role.ml_workflow
}

moved {
  from = module.iam_eks[0].aws_iam_role_policy.argo_workflows
  to   = module.iam_eks[0].aws_iam_role_policy.ml_workflow
}

# eks module から karpenter module へのリソース移行
moved {
  from = module.eks[0].aws_iam_role.karpenter
  to   = module.karpenter[0].aws_iam_role.karpenter
}

moved {
  from = module.eks[0].aws_iam_policy.karpenter
  to   = module.karpenter[0].aws_iam_policy.karpenter
}

moved {
  from = module.eks[0].aws_iam_role_policy_attachment.karpenter
  to   = module.karpenter[0].aws_iam_role_policy_attachment.karpenter
}

moved {
  from = module.eks[0].aws_eks_access_entry.karpenter_node
  to   = module.karpenter[0].aws_eks_access_entry.karpenter_node
}

moved {
  from = module.eks[0].aws_ec2_tag.karpenter_cluster_sg
  to   = module.karpenter[0].aws_ec2_tag.karpenter_cluster_sg
}

moved {
  from = module.eks[0].aws_iam_service_linked_role.spot
  to   = module.karpenter[0].aws_iam_service_linked_role.spot
}

moved {
  from = module.eks[0].aws_sqs_queue.karpenter
  to   = module.karpenter[0].aws_sqs_queue.karpenter
}

moved {
  from = module.eks[0].aws_sqs_queue_policy.karpenter
  to   = module.karpenter[0].aws_sqs_queue_policy.karpenter
}

moved {
  from = module.eks[0].aws_cloudwatch_event_rule.karpenter["spot_interruption"]
  to   = module.karpenter[0].aws_cloudwatch_event_rule.karpenter["spot_interruption"]
}

moved {
  from = module.eks[0].aws_cloudwatch_event_rule.karpenter["rebalance"]
  to   = module.karpenter[0].aws_cloudwatch_event_rule.karpenter["rebalance"]
}

moved {
  from = module.eks[0].aws_cloudwatch_event_rule.karpenter["instance_state"]
  to   = module.karpenter[0].aws_cloudwatch_event_rule.karpenter["instance_state"]
}

moved {
  from = module.eks[0].aws_cloudwatch_event_rule.karpenter["scheduled_change"]
  to   = module.karpenter[0].aws_cloudwatch_event_rule.karpenter["scheduled_change"]
}

moved {
  from = module.eks[0].aws_cloudwatch_event_target.karpenter["spot_interruption"]
  to   = module.karpenter[0].aws_cloudwatch_event_target.karpenter["spot_interruption"]
}

moved {
  from = module.eks[0].aws_cloudwatch_event_target.karpenter["rebalance"]
  to   = module.karpenter[0].aws_cloudwatch_event_target.karpenter["rebalance"]
}

moved {
  from = module.eks[0].aws_cloudwatch_event_target.karpenter["instance_state"]
  to   = module.karpenter[0].aws_cloudwatch_event_target.karpenter["instance_state"]
}

moved {
  from = module.eks[0].aws_cloudwatch_event_target.karpenter["scheduled_change"]
  to   = module.karpenter[0].aws_cloudwatch_event_target.karpenter["scheduled_change"]
}
