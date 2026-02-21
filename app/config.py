from pathlib import Path
import yaml
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv("secrets/.env")
env: str = os.getenv("ENV")

with Path(f"config/config-{env}.yaml").open("r", encoding="utf-8") as f:
    config = yaml.safe_load(f) or {}
config["openrouter_api_key"] = os.getenv("OPENROUTER_API_KEY")

class Settings(BaseSettings):
    openrouter_api_key: str = ""
    url: str = "http://localhost:8000"
    openrouter_url: str = "https://openrouter.ai/api/v1/chat/completions"
    models_url: str = "https://openrouter.ai/api/v1/models"
    db_path: str = "cvbot.db"
    data_dir: str = "data/candidates"
    env: str = "dev"

    class Config:
        env_file = "secrets/.env"


settings = Settings(**config)
