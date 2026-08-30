# Terraform 運用マニュアル

## フラグ早見表

| フラグ | デフォルト | 対象リソース |
|---|---|---|
| `compute_enabled` | `false` | EKS・NAT・IRSA・Bastion・RDS |
| `retain_on_idle` | `true` | ECR・Secrets Manager・pull-through cache |

## 状態パターン

| `compute_enabled` | `retain_on_idle` | 状態 |
|---|---|---|
| `true` | `true` | 全リソース稼働（通常運用） |
| `false` | `true` | EKS/RDS 停止・ECR は保持（短期停止） |
| `false` | `false` | ほぼ全削除（長期放置・コストゼロ） |

## よく使う操作

**停止（短期）**
```
terraform-apply: compute_enabled=false, retain_on_idle=true
```

**停止（長期・コストゼロ）**
```
terraform-apply: compute_enabled=false, retain_on_idle=false
```
> ⚠️ RDS はスナップショットを自動作成して削除。ECR イメージも全削除される。

**再開**
```
terraform-apply: compute_enabled=true
```
> ECR が空の場合は `deploy.yml` が自動トリガーされ、起動直後に数分 ImagePullBackOff になりうる（ArgoCD が自己修復）。

## GitHub Variables

| Variable | 管理方法 | 用途 |
|---|---|---|
| `COMPUTE_ENABLED_TEST/PROD` | apply 後に自動記録 | plan が現在の compute 状態を反映するための記録 |
| `RETAIN_ON_IDLE_TEST/PROD` | **手動で事前設定**（未設定時 `true`） | ECR/Secrets Manager を保持するか否かを制御 |
