"""Конфигурация сервиса. Все значения читаются из переменных окружения / `.env`."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    redis_host: str = "redis"
    redis_port: int = 6379

    kafka_bootstrap_servers: str
    kafka_topic_orders: str = "orders"

    jwt_secret: str
    jwt_ttl_minutes: int = 30

    # Список разрешённых Origin через запятую. Пусто — кросс-доменные запросы запрещены.
    cors_origins: str = ""

    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @property
    def celery_backend_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/1"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
