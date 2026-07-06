module "ml_data" {
  source = "./modules/ml_data"

  name_prefix = local.name_prefix
  github_repo = "daigo424/aily"
}

module "network" {
  count = local.is_test ? 1 : 0

  source      = "./modules/network"
  name_prefix = local.name_prefix
  vpc_cidr    = var.vpc_cidr
  azs         = ["us-west-2a", "us-west-2b", "us-west-2c"]
  create_nat  = var.compute_enabled
}

module "ecr" {
  count = local.is_test ? 1 : 0

  source                  = "./modules/ecr"
  name_prefix             = local.name_prefix
  docker_hub_username     = var.docker_hub_username
  docker_hub_access_token = var.docker_hub_access_token

  services = ["aily-api", "aily-frontend", "mlflow"]
}

module "bastion" {
  count = local.is_test ? 1 : 0

  source           = "./modules/bastion"
  name_prefix      = local.name_prefix
  vpc_id           = module.network[0].vpc_id
  public_subnet_id = module.network[0].public_subnet_ids[0]
}

module "rds" {
  count = local.is_test ? 1 : 0

  source             = "./modules/rds"
  name_prefix        = local.name_prefix
  vpc_id             = module.network[0].vpc_id
  vpc_cidr           = module.network[0].vpc_cidr
  private_subnet_ids = module.network[0].private_subnet_ids
  allowed_cidrs      = local.vpn_cidrs
}

module "eks" {
  count = local.create_compute ? 1 : 0

  source             = "./modules/eks"
  name_prefix        = local.name_prefix
  eks_version        = var.eks_version
  private_subnet_ids = module.network[0].private_subnet_ids
}

module "karpenter" {
  count = local.create_compute ? 1 : 0

  source                    = "./modules/karpenter"
  name_prefix               = local.name_prefix
  cluster_name              = module.eks[0].cluster_name
  cluster_arn               = module.eks[0].cluster_arn
  cluster_security_group_id = module.eks[0].cluster_security_group_id
  oidc_provider_arn         = module.eks[0].oidc_provider_arn
  oidc_provider_url         = module.eks[0].oidc_provider_url
  node_role_arn             = module.eks[0].node_role_arn
}

module "iam_eks" {
  count = local.create_compute ? 1 : 0

  source             = "./modules/iam_eks"
  name_prefix        = local.name_prefix
  oidc_provider_arn  = module.eks[0].oidc_provider_arn
  oidc_provider_url  = module.eks[0].oidc_provider_url
  ml_data_bucket_arn = module.ml_data.bucket_arn
  kms_key_arn        = module.ml_data.kms_key_arn
}

module "iam_role_sa" {
  count = local.create_compute ? 1 : 0

  source             = "./modules/iam_role_sa"
  name_prefix        = local.name_prefix
  oidc_provider_arn  = module.eks[0].oidc_provider_arn
  oidc_provider_url  = module.eks[0].oidc_provider_url
  ml_data_bucket_arn = module.ml_data.bucket_arn
  kms_key_arn        = module.ml_data.kms_key_arn
}

resource "aws_eks_addon" "s3_csi" {
  count = local.create_compute ? 1 : 0

  cluster_name             = module.eks[0].cluster_name
  addon_name               = "aws-mountpoint-s3-csi-driver"
  service_account_role_arn = module.iam_eks[0].s3_csi_role_arn

  depends_on = [module.eks[0]]
}
