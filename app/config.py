from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str

    GITHUB_CLIENT_ID: str
    GITHUB_CLIENT_SECRET: str

    ALGORITHM: str = "HS256"

    BACKEND_URL: str = "http://localhost:8081"
    FRONTEND_URL: str = "http://localhost:3000"

    # External API URLS
    GENDERIZE_BASE_URL: str = "https://api.genderize.io"
    AGIFY_BASE_URL: str = "https://api.agify.io"
    NATIONALIZE_BASE_URL: str = "https://api.nationalize.io"

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )


settings = Settings()
