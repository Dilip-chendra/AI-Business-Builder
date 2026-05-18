from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_name: str = "Autonomous Business Builder"
    app_version: str = "0.3.0"
    trusted_hosts_raw: str = Field(default="localhost,127.0.0.1,backend,test,testserver", alias="TRUSTED_HOSTS")
    secure_cookies: bool = False
    metrics_enabled: bool = True
    metrics_path: str = "/metrics"

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./autonomous_builder.db"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout_seconds: int = 30

    # ── AI ───────────────────────────────────────────────────────────────────
    ai_timeout_seconds: float = 25.0
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.1-8b-instant"
    featherless_enabled: bool = True
    featherless_api_key: str | None = None
    featherless_base_url: str = "https://api.featherless.ai/v1"
    featherless_general_model: str = "deepseek-ai/DeepSeek-V3-0324"
    featherless_coding_model: str = "Qwen/Qwen2.5-Coder-32B-Instruct"
    featherless_reasoning_model: str = "deepseek-ai/DeepSeek-V3-0324"
    featherless_marketing_model: str = "deepseek-ai/DeepSeek-V3-0324"
    featherless_browser_model: str = "deepseek-ai/DeepSeek-V3-0324"
    hf_api_key: str | None = None
    hf_base_url: str = "https://api-inference.huggingface.co/models"
    hf_model: str = "HuggingFaceH4/zephyr-7b-beta"
    # Maximum seconds to wait for HuggingFace (model cold-start can be slow)
    hf_timeout_seconds: float = 60.0
    # How many times to retry when HF returns "model is loading"
    hf_loading_retries: int = 3
    # Seconds to wait between loading retries
    hf_loading_retry_delay: float = 20.0

    # ── Security ─────────────────────────────────────────────────────────────
    encryption_key: str = "L8TfXm-wYy4tE7sRk9Zp1_vQh3_A5bCjO2NlM7gY4wQ="

    # ── Payments ─────────────────────────────────────────────────────────────
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    paypal_client_id: str | None = None
    paypal_client_secret: str | None = None
    paypal_env: str = "sandbox"
    paypal_webhook_id: str | None = None
    app_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"

    # ── URLs ─────────────────────────────────────────────────────────────────
    frontend_url: AnyHttpUrl | str = "http://localhost:3000"
    backend_url: AnyHttpUrl | str = "http://localhost:8000"
    cors_origins_raw: str = Field(default="http://localhost:3000,http://127.0.0.1:3000", alias="CORS_ORIGINS")

    # ── Auth (JWT) ────────────────────────────────────────────────────────────
    jwt_secret_key: str = "change-me-in-production-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24  # 24 hours

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 300  # 5 minutes
    redis_healthcheck_enabled: bool = True

    # ── Rate limiting ─────────────────────────────────────────────────────────
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 3600  # per hour

    # ── Email ─────────────────────────────────────────────────────────────────
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    email_from: str = "noreply@autonomousbusiness.ai"
    email_from_name: str = "Autonomous Business Builder"

    # ── File uploads (Supabase Storage) ──────────────────────────────────────
    supabase_url: str | None = None
    supabase_service_key: str | None = None
    supabase_storage_bucket: str = "product-images"

    # ── Celery ────────────────────────────────────────────────────────────────
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── Agent ─────────────────────────────────────────────────────────────────
    agent_loop_interval_seconds: int = 3600  # run agents every hour
    agent_max_actions_per_run: int = 5
    # Agent safety limits
    agent_max_steps: int = 10
    agent_max_requests_per_run: int = 20
    agent_max_tokens_per_run: int = 50_000
    agent_max_cost_usd: float = 0.50
    browser_agent_max_steps: int = 32
    browser_agent_max_steps_hard: int = 120
    browser_agent_extension_steps: int = 12
    browser_agent_wait_for_control_seconds: int = 180
    browser_max_tabs: int = 5
    browser_headless: bool = False
    browser_session_root: str = "./.runtime/browser-sessions"
    browser_reasoning_model: str = "llama3"
    browser_fast_reasoning_model: str | None = None
    browser_vision_model: str = "llava:13b"
    browser_vision_models: str = "minicpm-v,llava:13b"
    browser_vision_timeout_seconds: float = 5.0
    browser_vision_fallback_timeout_seconds: float = 8.0
    browser_vision_keep_alive: str = "-1m"
    browser_vision_num_predict: int = 64
    browser_vision_max_image_width: int = 960
    browser_vision_max_image_height: int = 960
    browser_vision_jpeg_quality: int = 45
    browser_planner_timeout_seconds: float = 14.0
    browser_planner_fast_timeout_seconds: float = 18.0
    browser_synthesis_timeout_seconds: float = 40.0
    browser_planner_num_predict: int = 180
    browser_planner_keep_alive: str = "-1m"

    # ── Image Generation ──────────────────────────────────────────────────────
    openai_api_key: str | None = None
    stability_api_key: str | None = None

    # ── Platform OAuth (add your own keys) ───────────────────────────────────
    linkedin_client_id: str | None = None
    linkedin_client_secret: str | None = None
    linkedin_redirect_uri: str = "http://localhost:8000/api/v1/integrations/linkedin/callback"
    twitter_client_id: str | None = None
    twitter_client_secret: str | None = None
    facebook_client_id: str | None = None
    facebook_client_secret: str | None = None
    instagram_client_id: str | None = None
    instagram_client_secret: str | None = None
    google_ads_client_id: str | None = None
    google_ads_client_secret: str | None = None
    meta_ads_client_id: str | None = None
    meta_ads_client_secret: str | None = None

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def trusted_hosts(self) -> list[str]:
        return [host.strip() for host in self.trusted_hosts_raw.split(",") if host.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def redis_available(self) -> bool:
        """True when a real Redis URL is configured (not the default localhost)."""
        return self.redis_url != "redis://localhost:6379/0" or self.is_production

    @property
    def resolved_database_url(self) -> str:
        url = self.database_url
        if not url.startswith("sqlite"):
            return url
        prefix, _, remainder = url.partition(":///")
        if not remainder:
            return url
        path = remainder
        if not path or path == ":memory:":
            return url
        if path.startswith("./"):
            path_obj = (BACKEND_ROOT / path[2:]).resolve()
        else:
            path_obj = Path(path)
            if not path_obj.is_absolute():
                path_obj = (BACKEND_ROOT / path).resolve()
        normalized = path_obj.as_posix()
        return f"{prefix}:///{normalized}"

    @property
    def resolved_browser_session_root(self) -> str:
        raw = Path(self.browser_session_root)
        if raw.is_absolute():
            return str(raw)
        return str((BACKEND_ROOT / raw).resolve())


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
