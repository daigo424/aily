from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    app_base_url: str = "http://localhost:8000"
    llm_provider: str = "vllm"
    llm_base_url: str = ""
    llm_api_key: str = "dummy"
    llm_model: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""
    db_host: str
    db_username: str
    db_password: str
    db_port: str
    app_db_name: str
    checkpointer_db_name: str
    timezone: str = "Asia/Tokyo"
    attachment_local_dir: str = "/app/data/app/message_attachments"
    ml_data_bucket: str = ""
    attachment_s3_prefix: str = "ml_data/app/message_attachments"
    cloudfront_url: str = ""
    searxng_url: str = ""

    @property
    def app_database_url(self) -> str:
        return f"postgresql://{self.db_username}:{self.db_password}@{self.db_host}:{self.db_port}/{self.app_db_name}"

    @property
    def checkpointer_database_url(self) -> str:
        return f"postgresql://{self.db_username}:{self.db_password}@{self.db_host}:{self.db_port}/{self.checkpointer_db_name}"


settings = Settings()  # type: ignore[call-arg]
