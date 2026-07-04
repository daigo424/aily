# EC2 Spot Service Linked Role は compute の有効・無効に関わらず削除しない
resource "aws_iam_service_linked_role" "spot" {
  aws_service_name = "spot.amazonaws.com"
}
