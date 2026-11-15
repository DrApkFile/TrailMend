from functools import lru_cache

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRAILMEND_", env_file=".env", extra="forbid", frozen=True)

    hydra_url: HttpUrl
    hydra_token: SecretStr
    hydra_graph_id: str = Field(default="default", min_length=1)
    hydra_cell_id: str = Field(default="cell-0", min_length=1)
    hydra_timeout_s: float = Field(default=30.0, gt=0, le=120)
    admin_token: SecretStr
    mend_config_path: str = "config/mend.toml"
    demo_seed: int = Field(default=1, ge=0)
    live_run_id: str = Field(default="live", min_length=1)
    ask_rate_per_minute: int = Field(default=60, ge=1, le=10_000)
    judge_rate_per_minute: int = Field(default=20, ge=1, le=10_000)


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
