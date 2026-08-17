from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Catalog service settings. Env: TI_CATALOG_DATABASE_URL."""

    model_config = SettingsConfigDict(env_prefix="TI_")

    catalog_database_url: str = "sqlite://"


settings = Settings()
