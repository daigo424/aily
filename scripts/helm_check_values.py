#!/usr/bin/env python3
"""
ArgoCD Application の valuesObject に定義されたキーが、
公式 Helm chart の values.yaml に存在するかを検証するスクリプト。

Usage:
    python helm_check_values.py <ref_yaml> <target_yaml> [--subchart <prefix>=<url_or_path> ...]

    ref_yaml    : 参照する公式 chart の values.yaml（URL またはローカルパス）
    target_yaml : 検証対象の ArgoCD Application YAML（URL またはローカルパス）

Examples:
    python helm_check_values.py \\
        https://raw.githubusercontent.com/prometheus-community/helm-charts/kube-prometheus-stack-87.7.0/charts/kube-prometheus-stack/values.yaml \\
        infra/k8s/apps/test/kube-prometheus-stack.yaml \\
        --subchart grafana=https://raw.githubusercontent.com/grafana-community/helm-charts/main/charts/grafana/values.yaml \\
        --subchart kube-state-metrics=https://raw.githubusercontent.com/prometheus-community/helm-charts/kube-state-metrics-7.5.1/charts/kube-state-metrics/values.yaml \\
        --subchart prometheus-node-exporter=https://raw.githubusercontent.com/prometheus-community/helm-charts/prometheus-node-exporter-4.55.0/charts/prometheus-node-exporter/values.yaml
"""

import argparse
import sys
import urllib.request
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def load_from(source: str) -> dict:
    """URL またはローカルパスから YAML を読み込む。"""
    if source.startswith("http://") or source.startswith("https://"):
        print(f"  Fetching: {source}")
        try:
            with urllib.request.urlopen(source, timeout=15) as resp:
                return yaml.safe_load(resp.read().decode("utf-8")) or {}
        except Exception as e:
            print(f"  ERROR: {source}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"  Loading:  {source}")
        try:
            with open(source, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            print(f"  ERROR: File not found: {source}", file=sys.stderr)
            sys.exit(1)


def build_key_index(data: Any, prefix: str = "") -> dict[str, Any]:
    """
    YAML 構造を { ドット記法キー: 値 } の辞書に展開する。
    values.yaml の末端値（空dict `{}` など）を保持し、free-form 判定に使う。
    """
    index: dict[str, Any] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            full_key = f"{prefix}.{k}" if prefix else k
            index[full_key] = v
            index.update(build_key_index(v, full_key))
    elif isinstance(data, list):
        for item in data:
            index.update(build_key_index(item, prefix))
    return index


def is_valid_key(key: str, ref_index: dict[str, Any]) -> bool:
    """
    キーが参照 values.yaml で有効かを判定する。

    有効条件:
    1. exact match でキーが存在する
    2. 祖先キーが存在し、その値が {} (free-form dict) である
       例: `resources: {}` の場合、`resources.requests.cpu` は有効
    """
    if key in ref_index:
        return True

    parts = key.split(".")
    for i in range(len(parts) - 1, 0, -1):
        ancestor = ".".join(parts[:i])
        if ancestor in ref_index:
            val = ref_index[ancestor]
            # 空dict / 空list / None = free-form（以下は何でも入れてよい）
            # 例: resources: {}  → requests.cpu など有効
            # 例: tolerations: [] → key/operator/value/effect など有効
            if val is None or val == {} or val == []:
                return True
            if isinstance(val, (dict, list)):
                return False
            return False

    return False


def check_keys(
    values_object: dict,
    ref_index: dict[str, Any],
    subchart_indexes: dict[str, dict[str, Any]],
) -> list[str]:
    """
    valuesObject の全キーを検証し、どの参照 yaml にも存在しないキーのリストを返す。

    サブチャートキー（例: grafana.*）は親チャートとサブチャートの両方で確認し、
    どちらかに存在すれば valid とする。
    """
    missing: list[str] = []
    my_index = build_key_index(values_object)

    for key in sorted(my_index.keys()):
        top = key.split(".")[0]

        if top in subchart_indexes:
            if is_valid_key(key, ref_index):
                continue
            sub_key = key[len(top) + 1:] if "." in key else ""
            if sub_key and is_valid_key(sub_key, subchart_indexes[top]):
                continue
            missing.append(key)
        else:
            if not is_valid_key(key, ref_index):
                missing.append(key)

    return missing


def main() -> None:
    parser = argparse.ArgumentParser(
        description="valuesObject のキーを公式 values.yaml と照合する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "ref_yaml",
        help="参照する公式 chart の values.yaml（URL またはローカルパス）",
    )
    parser.add_argument(
        "target_yaml",
        help="検証対象の ArgoCD Application YAML（URL またはローカルパス）",
    )
    parser.add_argument(
        "--subchart",
        action="append",
        metavar="PREFIX=URL_OR_PATH",
        default=[],
        help="サブチャートのプレフィックスと values.yaml（URL またはローカルパス）（複数指定可）",
    )
    args = parser.parse_args()

    # --subchart 解析
    subchart_map: dict[str, str] = {}
    for entry in args.subchart:
        if "=" not in entry:
            print(f"ERROR: --subchart の形式が不正です: {entry}", file=sys.stderr)
            sys.exit(1)
        prefix, source = entry.split("=", 1)
        subchart_map[prefix] = source

    # 参照 yaml（公式 chart）をロード
    print(f"\n=== 検証対象: {args.target_yaml} ===")
    print("\n[1] 参照 values.yaml を読み込み中...")
    ref_data = load_from(args.ref_yaml)
    ref_index = build_key_index(ref_data)

    # サブチャートをロード
    subchart_indexes: dict[str, dict[str, Any]] = {}
    if subchart_map:
        print("\n[2] サブチャート values.yaml を読み込み中...")
        for prefix, source in subchart_map.items():
            subchart_indexes[prefix] = build_key_index(load_from(source))

    # 検証対象（Application YAML）をロード
    print("\n[3] 検証対象 Application YAML を読み込み中...")
    app = load_from(args.target_yaml)
    try:
        values_object: dict = app["spec"]["source"]["helm"]["valuesObject"]
    except (KeyError, TypeError):
        print("ERROR: spec.source.helm.valuesObject が見つかりません", file=sys.stderr)
        sys.exit(1)

    if not values_object:
        print("valuesObject が空です")
        return

    print("\n[4] 検証中...")
    missing = check_keys(values_object, ref_index, subchart_indexes)

    print()
    if missing:
        print(f"[WARN] 参照 values.yaml に存在しないキー ({len(missing)} 件):")
        for k in missing:
            print(f"  ✗  {k}")
        sys.exit(1)
    else:
        print("[OK] valuesObject の全キーが参照 values.yaml に存在します")


if __name__ == "__main__":
    main()
