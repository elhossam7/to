from __future__ import annotations

from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Profile Extraction Console"
    data_dir: Path = Field(default=Path("data"), alias="DATA_DIR")
    ollama_url: str = Field(default="http://localhost:11434/api/generate", alias="OLLAMA_URL")
    ollama_model: str = Field(default="llama3.1", alias="OLLAMA_MODEL")
    ollama_timeout: float = Field(default=90.0, alias="OLLAMA_TIMEOUT")
    ollama_stream: bool = Field(default=True, alias="OLLAMA_STREAM")
    ollama_num_predict: int = Field(default=600, alias="OLLAMA_NUM_PREDICT")
    ollama_num_ctx: int = Field(default=4096, alias="OLLAMA_NUM_CTX")
    prompt_max_lines_per_doc: int = Field(default=80, alias="PROMPT_MAX_LINES_PER_DOC")
    prompt_max_chars: int = Field(default=6000, alias="PROMPT_MAX_CHARS")
    max_retries: int = Field(default=2, alias="MAX_RETRIES")
    max_file_size: int = Field(default=1_000_000, alias="MAX_FILE_SIZE")
    cors_origin: str = Field(default="http://localhost:5173", alias="CORS_ORIGIN")
    extraction_rules: str = Field(
        default=(
            "Extract only visible personal profile information from the raw text. Return JSON only. "
            "Do not add keys outside the schema. Use null or empty arrays for fields that are not visible."
        ),
        alias="EXTRACTION_RULES",
    )

    @property
    def inbox_dir(self) -> Path:
        return self.data_dir / "inbox"

    @property
    def profiles_dir(self) -> Path:
        return self.data_dir / "profiles"

    @property
    def audit_log(self) -> Path:
        return self.data_dir / "audit.log"

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origin.split(",") if origin.strip()]

    def ensure_dirs(self) -> None:
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.audit_log.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
