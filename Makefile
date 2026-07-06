SHELL := /bin/bash
-include .env
export

ATLAS := atlas
ATLAS_ENV := local
COMPOSE := docker compose -f infra/docker/docker-compose.local.yml
RUN := $(COMPOSE) run --rm --remove-orphans
EXEC := $(COMPOSE) exec
APP_DB_URL := postgresql://$(DB_USERNAME):$(DB_PASSWORD)@$(DB_HOST):$(DB_PORT)/$(APP_DB_NAME)?sslmode=$(DB_SSLMODE)
APP_ATLAS_DEV_DB_URL := postgresql://$(DB_USERNAME):$(DB_PASSWORD)@$(DB_DEV_HOST):$(DB_PORT)/$(APP_ATLAS_DEV_DB_NAME)?sslmode=$(DB_SSLMODE)

build:
	$(COMPOSE) build

build-api:
	$(COMPOSE) build api

build-no-cache:
	$(COMPOSE) build --no-cache

up:
	$(COMPOSE) up

down:
	$(COMPOSE) down

all-check: format test typecheck lint-fix

typecheck:
	$(RUN) api mypy ./src

format:
	$(RUN) api python -m ruff format ./src

format-check:
	$(RUN) api python -m ruff format ./src --check

lint:
	$(RUN) api python -m ruff check ./src

lint-fix:
	$(RUN) api python -m ruff check ./src --fix

test:
	$(RUN) api python -m pytest

atlas-version:
	$(RUN) atlas version

atlas-inspect:
	$(RUN) atlas schema inspect --env local

atlas-apply:
	$(RUN) atlas schema apply --env local --config "file://app/atlas.hcl"

atlas-apply-test:
	$(RUN) atlas schema apply --env test --config "file://app/atlas.hcl"

rm-volumes:
	docker compose -f infra/docker/docker-compose.local.yml down --volumes

ps:
	$(COMPOSE) ps

shell-%:
	$(EXEC) $* bash || $(EXEC) $* sh || $(EXEC) $* ash

shell-run-%:
	$(RUN) --entrypoint bash $* || $(RUN) --entrypoint sh $* || $(RUN) --entrypoint ash $*

db:
	$(EXEC) db psql "$(APP_DB_URL)"

db-atlas-dev:
	$(EXEC) db_dev psql "$(APP_ATLAS_DEV_DB_URL)"

# --- Support ---

draw-graph:
	$(RUN) api python scripts/draw_graph.py

# --- LLM ---

vllm-start:
	ollama run $(LLM_MODEL)

vllm-clear:
	ollama rm $(LLM_MODEL)

vllm-list:
	ollama list

# --- AWS / EKS / ArgoCD ---

AWS_ENV ?= test

get-caller-identity:
	aws sts get-caller-identity

rds-tunnel: check-aws-profile
	python scripts/rds_tunnel.py --env $(AWS_ENV)

check-aws-profile:
ifndef AWS_PROFILE
	$(error AWS_PROFILE が未設定です。export AWS_PROFILE=<profile> を実行するか、.env に AWS_PROFILE=<profile> を追記してください)
endif

kubeconfig: check-aws-profile
	aws eks update-kubeconfig --name $(shell aws eks list-clusters --region us-west-2 --query 'clusters[0]' --output text) --region us-west-2 --role-arn arn:aws:iam::$(shell aws sts get-caller-identity --query Account --output text):role/$(shell aws eks list-clusters --region us-west-2 --query 'clusters[0]' --output text)-eks-developer

argocd-ui: check-aws-profile kubeconfig
	@echo -----------------------------
	@echo ArgoCD UI: http://localhost:18080
	@echo Username:  admin
	kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | python -c "import sys,base64; print('Password:  ' + base64.b64decode(sys.stdin.read().strip()).decode())"
	@echo -----------------------------
	@echo Port-forward starting... Ctrl+C to stop
	python scripts/port_forward.py argocd-server argocd 18080:80

monitoring-ui: check-aws-profile kubeconfig
	@echo -----------------------------
	@echo Grafana UI: http://localhost:13000
	@echo Username:  admin
	@echo Password:  admin
	@echo -----------------------------
	@echo Port-forward starting... Ctrl+C to stop
	python scripts/port_forward.py monitoring-grafana monitoring 13000:80

mlflow-ui: check-aws-profile kubeconfig
	@echo -----------------------------
	@echo MLflow UI: http://localhost:15000
	@echo -----------------------------
	@echo Port-forward starting... Ctrl+C to stop
	python scripts/port_forward.py mlflow mlflow 15000:5000

argoworkflow-ui: check-aws-profile kubeconfig
	@echo -----------------------------
	@echo Argo Workflows UI: http://localhost:12000
	@echo -----------------------------
	@echo Port-forward starting... Ctrl+C to stop
	python scripts/port_forward.py argo-workflows-server argo 12000:2746

langfuse-ui: check-aws-profile kubeconfig
	@echo -----------------------------
	@echo Langfuse UI: http://localhost:13001
	@echo -----------------------------
	@echo Port-forward starting... Ctrl+C to stop
	python scripts/port_forward.py langfuse-web langfuse 13001:3000

frontend-ui: check-aws-profile kubeconfig
	@echo -----------------------------
	@echo Frontend UI: http://localhost:8502
	@echo -----------------------------
	@echo Port-forward starting... Ctrl+C to stop
	python scripts/port_forward.py aily-frontend aily 8502:80

# --- HuggingFace → S3 ---

check-hf-to-s3:
ifndef HF_MODEL_ID
	$(error HF_MODEL_ID が未設定です。.env に HF_MODEL_ID=<hf_repo_id> を追記してください (例: HF_MODEL_ID=meta-llama/Llama-3.2-11B-Vision-Instruct))
endif
ifndef ML_DATA_BUCKET
	$(error ML_DATA_BUCKET が未設定です。.env に ML_DATA_BUCKET=<bucket_name> を追記してください)
endif
ifndef HF_TOKEN
	@echo "警告: HF_TOKEN が未設定です。非公開/ゲート付きモデルはダウンロードできません"
endif

hf-to-s3: check-aws-profile check-hf-to-s3
	python scripts/hf_to_s3.py

# --- Terraform ---

terraform-fmt:
	terraform fmt -recursive ./infra/terraform

# --- Helm ---

HELM_VALUES_URL ?=
HELM_APP_YAML   ?=
HELM_SUBCHARTS  ?=

# HELM_VALUES_URL : 参照する公式 chart の values.yaml（URL またはローカルパス）
# HELM_APP_YAML   : 検証対象の ArgoCD Application YAML（URL またはローカルパス）
# HELM_SUBCHARTS  : サブチャートの --subchart 引数をまとめて渡す（スペース区切り）
#
# 使用例:
#   make check-helm-values \
#     HELM_VALUES_URL=https://raw.githubusercontent.com/prometheus-community/helm-charts/kube-prometheus-stack-87.7.0/charts/kube-prometheus-stack/values.yaml \
#     HELM_APP_YAML=infra/k8s/apps/test/kube-prometheus-stack.yaml \
#     HELM_SUBCHARTS='--subchart grafana=https://raw.githubusercontent.com/grafana-community/helm-charts/main/charts/grafana/values.yaml --subchart kube-state-metrics=https://raw.githubusercontent.com/prometheus-community/helm-charts/kube-state-metrics-7.5.1/charts/kube-state-metrics/values.yaml --subchart prometheus-node-exporter=https://raw.githubusercontent.com/prometheus-community/helm-charts/prometheus-node-exporter-4.55.0/charts/prometheus-node-exporter/values.yaml'

helm-check-values:
ifndef HELM_VALUES_URL
	$(error HELM_VALUES_URL が未設定です。make check-helm-values HELM_VALUES_URL=<url_or_path> HELM_APP_YAML=<path>)
endif
ifndef HELM_APP_YAML
	$(error HELM_APP_YAML が未設定です。make check-helm-values HELM_VALUES_URL=<url_or_path> HELM_APP_YAML=<path>)
endif
	python scripts/helm_check_values.py "$(HELM_VALUES_URL)" $(HELM_APP_YAML) $(HELM_SUBCHARTS)
