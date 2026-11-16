import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Agente Explorador de Gmail"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5433/plataforma_agente",
    )
    STORAGE_DIR: str = os.path.join(os.getcwd(), "almacenamiento_local")
    GMAIL_SCOPES: list[str] = ["https://www.googleapis.com/auth/gmail.readonly"]
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_CHAT_MODEL: str = "qwen2.5:3b"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    GMAIL_POLL_INTERVAL_SECONDS: int = 300

    class Config:
        env_file = ".env"


settings = Settings()
