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

    # If enabled, apply Alembic migrations on startup (best for Postgres/prod).
    # Note: do NOT enable this if you have an existing DB created via create_all
    # unless you have stamped/migrated it appropriately.
    run_migrations_on_startup: bool = False

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

    # JWT auth (used for OAuth logins + browser clients)
    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_access_token_minutes: int = 60
    jwt_issuer: str = "agentpress"
    jwt_audience: str = "agentpress"

    # Optional: store JWT in an HttpOnly cookie for browser clients.
    # If enabled, `require_auth` will also accept the cookie token when no
    # Authorization header is present.
    auth_cookie_enabled: bool = False
    auth_cookie_name: str = "agentpress_access_token"
    auth_cookie_samesite: str = "lax"  # lax|strict|none
    auth_cookie_domain: str | None = None
    auth_cookie_path: str = "/"

    # Optional: after OAuth callback, redirect to this URL instead of returning JSON.
    # When used with cookie auth, you can avoid exposing the token to the frontend.
    auth_redirect_success_url: str | None = None
    auth_redirect_error_url: str | None = None

    # OAuth (Authorization Code)
    oauth_pkce_enabled: bool = False

    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_redirect_uri: str | None = None

    github_oauth_client_id: str | None = None
    github_oauth_client_secret: str | None = None
    github_oauth_redirect_uri: str | None = None

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

    security_headers_enabled: bool = True
    hsts_enabled: bool = False
    hsts_max_age_seconds: int = 31_536_000  # 365 days

    # Audit logs (in-memory ring buffers)
    audit_enabled: bool = True
    audit_max_events: int = 2000

    # Optional dependency URLs (used for /health readiness checks)
    redis_url: str | None = None  # e.g. redis://redis:6379
    qdrant_url: str | None = None  # e.g. http://qdrant:6333
    healthcheck_timeout_seconds: float = 1.5


settings = Settings()
