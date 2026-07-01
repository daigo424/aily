from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    app_base_url: str = "http://localhost:8000"
    verify_token: str = ""
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_graph_api_version: str = "v24.0"
    llm_provider: str = "vllm"
    llm_base_url: str = ""
    llm_api_key: str = "dummy"
    llm_model: str = ""
    db_host: str
    db_username: str
    db_password: str
    db_port: str
    app_db_name: str
    cp_conversation_db_name: str
    timezone: str = "Asia/Tokyo"

    @property
    def app_database_url(self) -> str:
        return f"postgresql://{self.db_username}:{self.db_password}@{self.db_host}:{self.db_port}/{self.app_db_name}"

    @property
    def cp_conversation_database_url(self) -> str:
        return f"postgresql://{self.db_username}:{self.db_password}@{self.db_host}:{self.db_port}/{self.cp_conversation_db_name}"


settings = Settings()  # type: ignore[call-arg]
