from typing import cast

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    supabase_jwt_secret: str
    supabase_service_role_key: str          # Used ONLY for auth.admin.* operations
    groq_api_key: str
    gemini_api_key: str = ""   # Optional — fallback tier 3 and 4; app starts without it
    frontend_url: str = ""
    environment: str = "development"
    api_docs_enabled: bool = False
    cors_allowed_origins: str = ""
    csrf_token: str = "vitalnet-spa"

    @property
    def allowed_origins(self) -> list[str]:
        origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]

        if self.frontend_url:
            origins.append(self.frontend_url.rstrip("/"))

        if self.cors_allowed_origins:
            origins.extend(
                origin.strip().rstrip("/")
                for origin in self.cors_allowed_origins.split(",")
                if origin.strip()
            )

        # Stable dedupe order
        return list(dict.fromkeys(origins))

    model_config = SettingsConfigDict(env_file='.env.local', extra='ignore')


settings = cast(Settings, Settings())  # pyright: ignore[reportCallIssue]
