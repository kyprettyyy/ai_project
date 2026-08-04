"""EvalRoute evaluation service settings."""

from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import ConfigDict, computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "EvalRoute Evaluation"
    APP_VERSION: str = "1.0.0"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 9090

    DATABASE_URL: str = ""
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "evalroute_evaluation"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    REDIS_KEY_PREFIX: str = "evaluation:"

    GATEWAY_BASE_URL: str = "http://localhost:8123/api"
    GATEWAY_API_KEY: str = ""
    GATEWAY_INTERNAL_TOKEN: str = ""
    GATEWAY_TIMEOUT_SECONDS: int = 180

    SESSION_SECRET_KEY: str = ""
    SESSION_MAX_AGE: int = 86400
    SESSION_EXPIRE_SECONDS: int = 86400
    CORS_ORIGINS: str = "http://localhost:5172,http://localhost:5173,http://localhost:5174,http://127.0.0.1:5172,http://localhost:3000,http://localhost"

    TENCENT_COS_ACCESS_KEY: str = ""
    TENCENT_COS_SECRET_KEY: str = ""
    TENCENT_COS_REGION: str = "ap-guangzhou"
    TENCENT_COS_BUCKET: str = ""
    TENCENT_COS_HOST: str = ""

    @computed_field
    @property
    def effective_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        password = quote_plus(self.DB_PASSWORD) if self.DB_PASSWORD else ""
        return f"mysql+aiomysql://{self.DB_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def sync_database_url(self) -> str:
        return self.effective_database_url.replace("mysql+aiomysql", "mysql+pymysql", 1)

    @property
    def gateway_openai_base_url(self) -> str:
        return f"{self.GATEWAY_BASE_URL.rstrip('/')}/v1"

    @property
    def effective_cos_host(self) -> str:
        if self.TENCENT_COS_HOST.strip():
            return self.TENCENT_COS_HOST.rstrip("/")
        if self.TENCENT_COS_BUCKET and self.TENCENT_COS_REGION:
            return f"https://{self.TENCENT_COS_BUCKET}.cos.{self.TENCENT_COS_REGION}.myqcloud.com"
        return ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    model_config = ConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
