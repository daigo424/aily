"""
Hugging Face モデルを S3 にアップロードするスクリプト。
量子化オプションを指定すると、量子化後のモデルをアップロードする。

使い方:
  # FP16（そのままアップロード）
  HF_TOKEN=hf_xxx python scripts/hf_to_s3.py

  # AWQ量子化（INT4相当・vLLM推奨）
  HF_TOKEN=hf_xxx QUANTIZE=awq python scripts/hf_to_s3.py

  # INT8量子化（bitsandbytes）
  HF_TOKEN=hf_xxx QUANTIZE=int8 python scripts/hf_to_s3.py

  # INT4量子化（bitsandbytes NF4）
  HF_TOKEN=hf_xxx QUANTIZE=int4 python scripts/hf_to_s3.py

必要な AWS 権限:
  - s3:PutObject / s3:ListBucket (ml_data バケット)
  - kms:GenerateDataKey (ml_data バケットの KMS キー)

量子化には torch (CUDA) が必要です。
  AWQ:  pip install autoawq
  INT8/INT4: pip install bitsandbytes transformers

S3 保存先: FP16 → models/google/gemma-3-12b-it
           AWQ  → models/google/gemma-3-12b-it-awq
           INT8 → models/google/gemma-3-12b-it-int8
           INT4 → models/google/gemma-3-12b-it-int4
"""

import os
import shutil

import boto3
from huggingface_hub import snapshot_download
from tqdm import tqdm

# 環境変数から読み込む（Makefile / .env 経由で上書き可能）
# HF_MODEL_ID: HuggingFace repo ID (例: google/gemma-3-12b-it)
# QUANTIZE: 量子化方式（"int8" / "int4" / "" でFP16そのまま）
# ※ LLM_MODEL (GitHub Variable) にも同じ値を設定すること
HF_MODEL_ID = os.environ.get("HF_MODEL_ID", "").strip()
BUCKET_NAME = os.environ.get("ML_DATA_BUCKET", "").strip()
QUANTIZE = os.environ.get("QUANTIZE", "").strip().lower()  # "" / "int8" / "int4"
CLEANUP_LOCAL = True  # アップロード後にローカルの一時ファイルを削除するか

# S3 保存先: 量子化ありの場合はサフィックスで区別
_s3_model_name = f"{HF_MODEL_ID}-{QUANTIZE}" if QUANTIZE else HF_MODEL_ID
S3_PREFIX = f"models/{_s3_model_name}"


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


def _quantize_and_save(local_dir: str, quant_dir: str, quantize: str) -> None:
    """ダウンロード済みモデルを量子化して quant_dir に保存する（GPU必須）"""
    import torch

    if not torch.cuda.is_available():
        raise SystemExit("エラー: 量子化には CUDA GPU が必要です")

    if quantize == "awq":
        _quantize_awq(local_dir, quant_dir)
    elif quantize in ("int8", "int4"):
        _quantize_bnb(local_dir, quant_dir, quantize)
    else:
        raise SystemExit(f"エラー: QUANTIZE='{quantize}' は無効です（awq / int8 / int4 を指定してください）")


def _quantize_awq(local_dir: str, quant_dir: str) -> None:
    """AWQ量子化（INT4相当）: vLLMで --quantization awq として使用可能"""
    try:
        from awq import AutoAWQForCausalLM
    except ImportError:
        raise SystemExit("エラー: AWQ量子化には autoawq が必要です（pip install autoawq）")
    from transformers import AutoTokenizer

    print("   AWQモデルをロード中...")
    tokenizer = AutoTokenizer.from_pretrained(local_dir)
    model = AutoAWQForCausalLM.from_pretrained(
        local_dir, safetensors=True, device_map="auto", low_cpu_mem_usage=True, use_cache=False
    )

    quant_config = {"zero_point": True, "q_group_size": 128, "w_bit": 4, "version": "GEMM"}
    print("   AWQ量子化中（数十分かかる場合があります）...")
    model.quantize(tokenizer, quant_config=quant_config)

    print(f"   量子化済みモデルを保存中: {quant_dir}")
    model.save_quantized(quant_dir)
    tokenizer.save_pretrained(quant_dir)
    print("   保存完了")


def _quantize_bnb(local_dir: str, quant_dir: str, quantize: str) -> None:
    """bitsandbytes量子化（INT8 / INT4 NF4）"""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    if quantize == "int8":
        quant_config = BitsAndBytesConfig(load_in_8bit=True)
    else:
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
        )

    print(f"   モデルをロード中（{quantize.upper()} 量子化）...")
    tokenizer = AutoTokenizer.from_pretrained(local_dir)
    model = AutoModelForCausalLM.from_pretrained(
        local_dir,
        quantization_config=quant_config,
        device_map="auto",
    )

    print(f"   量子化済みモデルを保存中: {quant_dir}")
    tokenizer.save_pretrained(quant_dir)
    model.save_pretrained(quant_dir)
    print("   保存完了")


def _upload_dir(s3_client, local_dir: str, bucket_name: str, s3_prefix: str) -> None:
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


def download_and_upload_to_s3(model_id: str, bucket_name: str, s3_prefix: str) -> None:
    local_dir = f"./temp_{model_id.replace('/', '_')}"
    quant_dir = f"{local_dir}-{QUANTIZE}" if QUANTIZE else None

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

    # 2. 量子化（オプション）
    upload_dir = local_dir
    if QUANTIZE and quant_dir:
        print(f"\n2. {QUANTIZE.upper()} 量子化中...")
        _quantize_and_save(local_dir, quant_dir, QUANTIZE)
        upload_dir = quant_dir

    # 3. S3 アップロード
    step = 3 if QUANTIZE else 2
    s3_client = boto3.client("s3")
    print(f"\n{step}. S3 バケット '{bucket_name}/{s3_prefix}' へアップロード中...")
    print("   既に存在するファイルはスキップします\n")
    _upload_dir(s3_client, upload_dir, bucket_name, s3_prefix)
    print(f"→ GitHub Variable LLM_MODEL にも同じ値を設定してください: {s3_prefix.removeprefix('models/')}")

    # 4. ローカルの一時ファイルを削除
    if CLEANUP_LOCAL:
        step += 1
        print(f"\n{step}. ローカル一時ファイルを削除中...")
        shutil.rmtree(local_dir)
        if quant_dir and os.path.exists(quant_dir):
            shutil.rmtree(quant_dir)


if __name__ == "__main__":
    if not HF_MODEL_ID:
        raise SystemExit("エラー: HF_MODEL_ID が未設定です (例: HF_MODEL_ID=google/gemma-3-12b-it)")
    if not BUCKET_NAME:
        raise SystemExit("エラー: ML_DATA_BUCKET が未設定です")
    if QUANTIZE and QUANTIZE not in ("awq", "int8", "int4"):
        raise SystemExit(f"エラー: QUANTIZE='{QUANTIZE}' は無効です（awq / int8 / int4 を指定してください）")
    download_and_upload_to_s3(HF_MODEL_ID, BUCKET_NAME, S3_PREFIX)
