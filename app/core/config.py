from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5435/eve_healthcare"
    TEST_DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5435/eve_healthcare_test"
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60
    WEBHOOK_SECRET: str = "change-me"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
