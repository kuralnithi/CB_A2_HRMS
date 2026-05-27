from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "supersecretkey_please_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30 * 24 * 60 # 30 days
    
    # Optional Database Connection String (ideal for cloud deployment)
    DATABASE_URL: str = ""
    
    # PostgreSQL Configuration (fallback for local development)
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "hr_copilot"
    POSTGRES_PORT: str = "5432"
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            # Replace standard postgresql:// or postgres:// prefix with postgresql+asyncpg:// for async compatibility
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            
            # Clean up parameters like sslmode and channel_binding that asyncpg does not support in URL
            if "?" in url:
                base_url, query_params = url.split("?", 1)
                import urllib.parse
                params = urllib.parse.parse_qs(query_params)
                # Remove parameters that cause TypeError in asyncpg
                params.pop("sslmode", None)
                params.pop("channel_binding", None)
                # Re-encode parameters
                if params:
                    new_query = urllib.parse.urlencode(params, doseq=True)
                    url = f"{base_url}?{new_query}"
                else:
                    url = base_url
            return url
            
        import urllib.parse
        encoded_password = urllib.parse.quote_plus(self.POSTGRES_PASSWORD)
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{encoded_password}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # LLM & Qdrant
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""
    # Redis Cache
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_POLICY: int = 900  # 15 minutes
    CACHE_TTL_SQL: int = 300     # 5 minutes
    ENABLE_CACHE: bool = True
    
    class Config:
        env_file = ".env"

settings = Settings()
