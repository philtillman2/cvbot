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
smtp_config = config.pop("smtp", {}) or {}
contact_config = config.pop("contact", {}) or {}
config["smtp_host"] = smtp_config.get("host") or ""
config["smtp_port"] = int(smtp_config.get("port", 587))
config["smtp_username"] = ""
config["smtp_password"] = ""
smtp_use_tls = smtp_config.get("use_tls", True)
if isinstance(smtp_use_tls, str):
    config["smtp_use_tls"] = smtp_use_tls.lower() in {"1", "true", "yes", "on"}
else:
    config["smtp_use_tls"] = bool(smtp_use_tls)
config["contact_email_from"] = contact_config.get("email_from", "")
config["contact_email_to"] = contact_config.get("email_to", "")
min_submit_time_enabled = contact_config.get("min_submit_time_enabled", True)
if isinstance(min_submit_time_enabled, str):
    config["contact_min_submit_time_enabled"] = min_submit_time_enabled.lower() in {"1", "true", "yes", "on"}
else:
    config["contact_min_submit_time_enabled"] = bool(min_submit_time_enabled)
config["contact_min_submit_time_seconds"] = int(contact_config.get("min_submit_time_seconds", 3))
turnstile_enabled = contact_config.get("turnstile_enabled", False)
if isinstance(turnstile_enabled, str):
    config["contact_turnstile_enabled"] = turnstile_enabled.lower() in {"1", "true", "yes", "on"}
else:
    config["contact_turnstile_enabled"] = bool(turnstile_enabled)
config["contact_turnstile_site_key"] = contact_config.get("turnstile_site_key", "")

if smtp_host := os.getenv("SMTP_HOST"):
    config["smtp_host"] = smtp_host
if smtp_port := os.getenv("SMTP_PORT"):
    config["smtp_port"] = int(smtp_port)
if smtp_username := os.getenv("SMTP_USERNAME"):
    config["smtp_username"] = smtp_username
if smtp_password := os.getenv("SMTP_PASSWORD"):
    config["smtp_password"] = smtp_password
if smtp_use_tls := os.getenv("SMTP_USE_TLS"):
    config["smtp_use_tls"] = smtp_use_tls.lower() in {"1", "true", "yes", "on"}
if contact_email_from := os.getenv("CONTACT_EMAIL_FROM"):
    config["contact_email_from"] = contact_email_from
if contact_email_to := os.getenv("CONTACT_EMAIL_TO"):
    config["contact_email_to"] = contact_email_to
if contact_turnstile_site_key := os.getenv("CONTACT_TURNSTILE_SITE_KEY"):
    config["contact_turnstile_site_key"] = contact_turnstile_site_key
if contact_turnstile_secret_key := os.getenv("CONTACT_TURNSTILE_SECRET_KEY"):
    config["contact_turnstile_secret_key"] = contact_turnstile_secret_key

class Settings(BaseSettings):
    openrouter_api_key: str = ""
    url: str = "http://localhost:8000"
    openrouter_url: str = "https://openrouter.ai/api/v1/chat/completions"
    models_url: str = "https://openrouter.ai/api/v1/models"
    max_daily_cost_usd: float = 5.0
    db_path: str = "cvbot.db"
    data_dir: str = "data/candidates"
    env: str = "dev"
    models: dict[str, str] = {}
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    contact_email_from: str = ""
    contact_email_to: str = ""
    contact_min_submit_time_enabled: bool = True
    contact_min_submit_time_seconds: int = 3
    contact_turnstile_enabled: bool = False
    contact_turnstile_site_key: str = ""
    contact_turnstile_secret_key: str = ""
    contact_turnstile_challenge_url: str = ""

    class Config:
        env_file = "secrets/.env"


settings = Settings(**config)
