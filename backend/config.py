from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    supabase_jwt_secret: str
    supabase_service_role_key: str          # NEW — used ONLY for auth.admin.* operations
    groq_api_key: str

    model_config = SettingsConfigDict(env_file='.env.local', extra='ignore')

settings = Settings()
