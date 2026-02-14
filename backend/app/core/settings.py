from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENTPRESS_", env_file=".env", extra="ignore")

    database_url: str = Field(
        default="sqlite+aiosqlite:///./.data/agentpress.db",
        validation_alias=AliasChoices("AGENTPRESS_DATABASE_URL", "DATABASE_URL"),
    )
    auto_create_tables: bool = True

    plugins_dir: Path = Path("../plugins/installed")
    plugin_timeout_seconds: int = 30
    plugin_max_output_bytes: int = 2_000_000

    llm_provider: str = "ollama"  # ollama | openai | anthropic
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    embeddings_provider: str = "sentence-transformers"
    embeddings_model: str = "all-MiniLM-L6-v2"

    tool_calling_mode: str = "manual"  # manual | auto | disabled

    # Optional API key for protecting the HTTP API.
    # If unset, all requests are allowed.
    api_key: str | None = None

    # HTTP security hardening
    max_request_body_bytes: int = 1_000_000  # ~1MB
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 120
    trust_proxy_headers: bool = False

    # API surface hardening
    enable_docs: bool = True

    # CORS (disabled by default; explicitly enable + set origins for browsers)
    cors_enabled: bool = False
    cors_allow_origins: list[str] = []
    cors_allow_methods: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_allow_headers: list[str] = ["*"]
    cors_allow_credentials: bool = False


settings = Settings()
