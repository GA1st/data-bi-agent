from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4"
    llm_temperature: float = 0.0

    # Database
    database_url: str = "sqlite+aiosqlite:///data/demo.db"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True

    # Auth
    auth_enabled: bool = False
    auth_api_key: str = ""

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_max_requests: int = 60
    rate_limit_window_seconds: int = 60

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Cache
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300
    cache_max_size: int = 128

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
