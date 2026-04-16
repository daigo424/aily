from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    app_base_url: str = "http://localhost:8000"
    verify_token: str
    whatsapp_token: str
    whatsapp_phone_number_id: str
    whatsapp_graph_api_version: str = "v24.0"
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"
    app_db_host: str
    app_db_name: str
    app_db_username: str
    app_db_password: str
    app_db_port: str
    timezone: str = "Asia/Tokyo"

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.app_db_username}:{self.app_db_password}@{self.app_db_host}:{self.app_db_port}/{self.app_db_name}"


settings = Settings() # type: ignore[call-arg]
