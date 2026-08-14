from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TI_")

    jwt_secret: str = "dev-secret-change-me"
    demo_username: str = "demo"
    demo_password: str = "demo123"
    packs_root: str = "packs"
    database_url: str = "sqlite://"
    llm_api_key: str = ""
    llm_base_url: str | None = None
    llm_model: str = "gpt-4o-mini"


settings = Settings()
