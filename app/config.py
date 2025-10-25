"""Application configuration."""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings."""

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/epub_editor.db"

    # Security
    secret_key: str = "your-secret-key-change-in-production"
    encryption_key: str = "your-encryption-key-change-in-production"

    # Application
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    # File Upload
    max_upload_size: int = 100_000_000  # 100MB
    allowed_extensions: str = "epub"  # Can be comma-separated list

    # Processing
    max_workers: int = 5
    default_max_tokens: int = 4096
    safety_buffer: int = 500

    # CORS
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    def get_cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # Paths
    data_dir: str = "./data"
    projects_dir: str = "./data/projects"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
