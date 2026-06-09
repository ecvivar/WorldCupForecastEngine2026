from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    project_name: str = "WorldCup Forecast Engine 2026"
    project_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    debug: bool = False

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/worldcup_forecast"
    database_echo: bool = False
    database_pool_size: int = 10
    database_max_overflow: int = 20

    redis_url: str = "redis://localhost:6379/0"
    cache_ttl: int = 300

    collectors_fifa_base_url: str = "https://api.fifa.com/api/v3"
    collectors_elo_base_url: str = "https://www.eloratings.net"
    collectors_fbref_base_url: str = "https://fbref.com"
    collectors_transfermarkt_base_url: str = "https://transfermarkt.com"
    collectors_football_data_base_url: str = "https://api.football-data.org/v4"
    collectors_football_data_api_key: str = ""

    collectors_rate_limit_per_second: int = 5
    collectors_retry_max_attempts: int = 3
    collectors_retry_backoff: float = 2.0

    engine_default_simulations: int = 100_000
    engine_poisson_max_goals: int = 10
    engine_elo_k_factor: int = 32
    engine_elo_initial_rating: int = 1500

    igf_elo_weight: float = 0.25
    igf_recent_form_weight: float = 0.20
    igf_xg_weight: float = 0.12
    igf_xga_weight: float = 0.08
    igf_opponent_strength_weight: float = 0.10
    igf_world_cup_experience_weight: float = 0.10
    igf_squad_quality_weight: float = 0.10
    igf_tournament_history_weight: float = 0.05

    secret_key: str = "change-me-in-production"
    log_level: str = "INFO"

    cors_origins: str = "http://localhost:3000,http://localhost:3001"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings()
