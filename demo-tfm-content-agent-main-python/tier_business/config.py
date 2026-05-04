import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.environ.get("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_JWT_SECRET: str = os.environ.get("SUPABASE_JWT_SECRET", "")

    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    LOVABLE_API_KEY: str = os.environ.get("LOVABLE_API_KEY", "")

    SECRET_KEY: str = os.environ.get(
        "SECRET_KEY", "cambia-esto-por-una-clave-secreta-muy-larga"
    )
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development")
    PORT: int = int(os.environ.get("PORT", "8000"))


settings = Settings()
