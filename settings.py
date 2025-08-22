from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    AZURE_OPENAI_API_KEY: str
    DISCORD_API_KEY: str
    DISCORD_ANNOUNCE_CHANNEL_ID: int
    DISCORD_GUILD_ID: int
    DISCORD_QUEUE_CHANNEL_ID: int
    DISCORD_VOICE_CHANNEL_ID: int

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()  # type: ignore
