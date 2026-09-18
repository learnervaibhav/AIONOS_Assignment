"""
Application configuration -- reads from .env file.
Supports both GEMINI_API_KEY and GOOGLE_API_KEY env var names.
"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    gemini_api_key: str = ""
    google_api_key: str = ""          # Alias used in .env
    database_url: str = "sqlite:///./airline_agent.db"
    app_name: str = "Airline Disruption Resolution Agent"
    debug: bool = False

    def get_api_key(self) -> str:
        """Return whichever API key is set (GEMINI_API_KEY or GOOGLE_API_KEY)."""
        return self.gemini_api_key or self.google_api_key


settings = Settings()

