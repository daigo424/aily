import os

import httpx

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


def api_get(path: str, params: dict | None = None) -> dict:
    resp = httpx.get(f"{API_BASE_URL}{path}", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, data: dict) -> dict:
    resp = httpx.post(f"{API_BASE_URL}{path}", json=data, timeout=30)
    resp.raise_for_status()
    return resp.json()


def api_patch(path: str, data: dict) -> dict:
    resp = httpx.patch(f"{API_BASE_URL}{path}", json=data, timeout=30)
    resp.raise_for_status()
    return resp.json()
