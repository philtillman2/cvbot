from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    openrouter_api_key: str = ""
    db_path: str = "cvbot.db"
    data_dir: str = "data/candidates"

    class Config:
        env_file = ".env"


settings = Settings()
