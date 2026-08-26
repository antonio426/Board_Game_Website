from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Board Game Website API"
    MONGO_URI: str = "mongodb://boardgame:boardgame_dev@localhost:27017"
    MONGO_DB_NAME: str = "boardgame"
    QDRANT_URL: str = "http://localhost:6333"
    REDIS_URL: str = "redis://localhost:6379/0"
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    JWT_SECRET: str = "change-this-to-a-random-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"
    BGG_USERNAME: str = ""
    BGG_PASSWORD: str = ""
    BGG_SESSION_COOKIES: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
