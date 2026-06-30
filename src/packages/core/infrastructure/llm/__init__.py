from packages.core.config import settings

if settings.llm_provider == "vllm":
    from .llm_client import vllm_client as client
else:
    from .llm_client import openai_client as client

__all__ = ["client"]
