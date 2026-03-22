from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/engram"
    redis_url: str = "redis://localhost:6379/0"

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    engram_encryption_key: str = ""

    chunk_size_tokens: int = 500
    chunk_overlap_tokens: int = 50
    memory_decay_halflife_days: int = 365
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    generation_provider: str = "openai"
    generation_model: str = "gpt-4.1"

    photo_storage_dir: str = "~/.engram/photos"

    server_host: str = "0.0.0.0"
    server_port: int = 8000
    mcp_transport: str = "stdio"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
