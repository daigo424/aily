from datetime import datetime, timezone


def normalize_message(message: dict) -> dict:
    msg_type = message.get("type", "unknown")
    normalized = {
        "message_type": msg_type,
        "text": None,
        "image": None,
        "audio": None,
        "interactive": None,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    if msg_type == "text":
        normalized["text"] = message.get("text", {}).get("body")
    elif msg_type == "image":
        normalized["image"] = message.get("image", {})
    elif msg_type == "audio":
        normalized["audio"] = message.get("audio", {})
    elif msg_type == "interactive":
        normalized["interactive"] = message.get("interactive", {})
    return normalized
