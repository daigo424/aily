"""
Hugging Face モデルを S3 にアップロードするスクリプト。
量子化オプションを指定すると、量子化後のモデルをアップロードする。

使い方:
  # FP16（そのままアップロード）
  HF_TOKEN=hf_xxx python scripts/hf_to_s3.py

  # W8A8 INT8量子化（llm-compressor・vLLM推奨）
  HF_TOKEN=hf_xxx QUANTIZE=w8a8 python scripts/hf_to_s3.py

  # INT8量子化（bitsandbytes）
  HF_TOKEN=hf_xxx QUANTIZE=int8 python scripts/hf_to_s3.py

  # INT4量子化（bitsandbytes NF4）
  HF_TOKEN=hf_xxx QUANTIZE=int4 python scripts/hf_to_s3.py

必要な AWS 権限:
  - s3:PutObject / s3:ListBucket (ml_data バケット)
  - kms:GenerateDataKey (ml_data バケットの KMS キー)

量子化には torch (CUDA) が必要です。
  W8A8: pip install llmcompressor datasets
  INT8/INT4: pip install bitsandbytes transformers

S3 保存先: FP16  → models/google/gemma-3-12b-it
           W8A8  → models/google/gemma-3-12b-it-w8a8
           INT8  → models/google/gemma-3-12b-it-int8
           INT4  → models/google/gemma-3-12b-it-int4
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
QUANTIZE = os.environ.get("QUANTIZE", "").strip().lower()  # "" / "w8a8" / "int8" / "int4"
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

    if quantize == "w8a8":
        _quantize_w8a8(local_dir, quant_dir)
    elif quantize in ("int8", "int4"):
        _quantize_bnb(local_dir, quant_dir, quantize)
    else:
        raise SystemExit(f"エラー: QUANTIZE='{quantize}' は無効です（w8a8 / int8 / int4 を指定してください）")


def _quantize_w8a8(local_dir: str, quant_dir: str) -> None:
    """W8A8 INT8量子化（llm-compressor）: vLLMで --quantization compressed-tensors として使用可能

    SmoothQuantModifier は Gemma 3 のマルチモーダル構造（model.language_model.layers.*）に
    対して自動マッピング推論が失敗するため使用しない。
    RedHatAI/gemma-3-12b-it-quantized.w8a8 の公式レシピに準拠。
    """
    try:
        from llmcompressor import oneshot
        from llmcompressor.modifiers.quantization import GPTQModifier
    except ImportError:
        raise SystemExit("エラー: W8A8量子化には llmcompressor が必要です（pip install llmcompressor datasets）")
    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer

    NUM_CALIBRATION_SAMPLES = 512
    MAX_SEQUENCE_LENGTH = 1024

    print("   モデルをロード中...")
    tokenizer = AutoTokenizer.from_pretrained(local_dir)
    model = AutoModelForCausalLM.from_pretrained(local_dir, device_map="auto", torch_dtype="auto")

    print("   キャリブレーションデータを準備中...")
    # streaming=True で必要なサンプルだけ取得（全スプリット480k+のDLを回避）
    raw_iter = load_dataset("HuggingFaceH4/ultrachat_200k", split="train_sft", streaming=True)
    raw_iter = raw_iter.shuffle(seed=42, buffer_size=10_000)
    from datasets import Dataset
    ds = Dataset.from_list(list(raw_iter.take(NUM_CALIBRATION_SAMPLES)))
    ds = ds.map(lambda ex: {"text": tokenizer.apply_chat_template(ex["messages"], tokenize=False)})
    ds = ds.map(
        lambda s: tokenizer(s["text"], padding=False, max_length=MAX_SEQUENCE_LENGTH, truncation=True, add_special_tokens=False),
        remove_columns=ds.column_names,
    )

    print("   W8A8量子化中（数十分〜1時間程度かかります）...")
    # Gemma 3 (VLM) 専用設定:
    #   - vision_tower / multi_modal_projector / embed_tokens は量子化対象外
    #   - sequential_targets は oneshot() に渡す（GPTQModifier のフィールドではない）
    recipe = [
        GPTQModifier(
            targets="Linear",
            scheme="W8A8",
            ignore=["re:.*lm_head.*", "re:.*embed_tokens.*", "re:vision_tower.*", "re:multi_modal_projector.*"],
            dampening_frac=0.01,
        ),
    ]
    oneshot(
        model=model,
        dataset=ds,
        recipe=recipe,
        max_seq_length=MAX_SEQUENCE_LENGTH,
        num_calibration_samples=NUM_CALIBRATION_SAMPLES,
        sequential_targets=["Gemma3DecoderLayer"],
    )

    print(f"   量子化済みモデルを保存中: {quant_dir}")
    model.save_pretrained(quant_dir, save_compressed=True)
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
    if QUANTIZE and QUANTIZE not in ("w8a8", "int8", "int4"):
        raise SystemExit(f"エラー: QUANTIZE='{QUANTIZE}' は無効です（w8a8 / int8 / int4 を指定してください）")
    download_and_upload_to_s3(HF_MODEL_ID, BUCKET_NAME, S3_PREFIX)
