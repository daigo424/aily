"""
Hugging Face モデルを S3 にアップロードするスクリプト。

使い方:
  HF_TOKEN=hf_xxx python scripts/hf_to_s3.py

必要な AWS 権限:
  - s3:PutObject / s3:ListBucket (ml_data バケット)
  - kms:GenerateDataKey (ml_data バケットの KMS キー)
"""

import os
import shutil

import boto3
from huggingface_hub import snapshot_download
from tqdm import tqdm

# 環境変数から読み込む（Makefile / .env 経由で上書き可能）
# HF_MODEL_ID: HuggingFace repo ID (例: Qwen/Qwen2.5-VL-7B-Instruct)
# ※ LLM_MODEL (GitHub Variable) にも同じ値を設定すること
HF_MODEL_ID = os.environ.get("HF_MODEL_ID", "").strip()
BUCKET_NAME = os.environ.get("ML_DATA_BUCKET", "").strip()
S3_PREFIX = f"models/{HF_MODEL_ID}"
CLEANUP_LOCAL = True  # アップロード後にローカルの一時ファイルを削除するか


def upload_file_to_s3(s3_client, local_path: str, bucket: str, key: str) -> bool:
    """ファイルを S3 にアップロード。既存ファイルはスキップ。True=アップロード済み、False=スキップ"""
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return False  # 既に存在する
    except s3_client.exceptions.ClientError:
        pass  # 存在しないのでアップロードへ

    file_size = os.path.getsize(local_path)
    with tqdm(total=file_size, unit="B", unit_scale=True, desc=os.path.basename(local_path)) as pbar:
        s3_client.upload_file(
            Filename=local_path,
            Bucket=bucket,
            Key=key,
            Callback=lambda n: pbar.update(n),
        )
    return True


def download_and_upload_to_s3(model_id: str, bucket_name: str, s3_prefix: str) -> None:
    local_dir = f"./temp_{model_id.replace('/', '_')}"

    # 1. HuggingFace からダウンロード
    hf_token = os.environ.get("HF_TOKEN")
    print(f"1. Hugging Face から {model_id} をダウンロード中...")
    print(f"   保存先: {local_dir}")
    if not hf_token:
        print("   ⚠️  HF_TOKEN が未設定です。非公開/ゲートモデルはダウンロードできません")

    snapshot_download(
        repo_id=model_id,
        local_dir=local_dir,
        token=hf_token,
        ignore_patterns=["*.msgpack", "*.h5", "*.ot"],
    )

    # 2. S3 アップロード
    s3_client = boto3.client("s3")
    print(f"\n2. S3 バケット '{bucket_name}/{s3_prefix}' へアップロード中...")
    print("   既に存在するファイルはスキップします\n")

    uploaded = skipped = 0
    for root, _, files in os.walk(local_dir):
        for file in files:
            local_path = os.path.join(root, file)
            relative_path = os.path.relpath(local_path, local_dir).replace("\\", "/")
            s3_key = f"{s3_prefix}/{relative_path}"

            if upload_file_to_s3(s3_client, local_path, bucket_name, s3_key):
                uploaded += 1
            else:
                print(f"   スキップ (既存): {s3_key}")
                skipped += 1

    print(f"\n完了: {uploaded} ファイルアップロード、{skipped} ファイルスキップ")
    print(f"S3 パス: s3://{bucket_name}/{s3_prefix}")
    print(f"→ GitHub Variable LLM_MODEL にも同じ値を設定してください: {model_id}")

    # 3. ローカルの一時ファイルを削除
    if CLEANUP_LOCAL:
        print(f"\n3. ローカル一時ファイルを削除中: {local_dir}")
        shutil.rmtree(local_dir)


if __name__ == "__main__":
    if not HF_MODEL_ID:
        raise SystemExit("エラー: HF_MODEL_ID が未設定です (例: HF_MODEL_ID=Qwen/Qwen2.5-VL-7B-Instruct)")
    if not BUCKET_NAME:
        raise SystemExit("エラー: ML_DATA_BUCKET が未設定です")
    download_and_upload_to_s3(HF_MODEL_ID, BUCKET_NAME, S3_PREFIX)
