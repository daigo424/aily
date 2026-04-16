import socket


def is_debug_server_ready(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.1):
            return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False
