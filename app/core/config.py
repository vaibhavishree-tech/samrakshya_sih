from pydantic_settings import BaseSettings, SettingsConfigDict

from pathlib import Path

print("Current working directory:", Path.cwd())
print(".env exists:", Path(".env").exists())
print(".env path:", Path(".env").resolve())

class Settings(BaseSettings):
    PROJECT_NAME: str = "सामरक्ष्य (Sāmarakṣya) OSINT Engine"
    API_V1_STR: str = "/api/v1"
    GROQ_API_KEY: str
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()

print("GROQ KEY LOADED:", bool(settings.GROQ_API_KEY))
print("GROQ KEY PREFIX:", settings.GROQ_API_KEY[:8])