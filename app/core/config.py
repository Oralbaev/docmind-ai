from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    gemini_api_key: str
    gemini_embedding_model: str = "gemini-embedding-2"
    gemini_llm_model: str = "gemini-3.5-flash-lite"
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    cors_allowed_origins: str = ""
    trust_proxy_headers: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
