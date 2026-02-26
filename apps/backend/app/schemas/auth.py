"""Authentication request and response schemas."""

from pydantic import BaseModel, EmailStr, field_validator


class SignupRequest(BaseModel):
    """Signup payload."""

    email: EmailStr
    password: str
    llm_provider: str = "openai"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_api_base: str | None = None
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    telegram_webhook_url: str = ""

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    """Login payload."""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Token refresh payload."""

    refresh_token: str


class TokenResponse(BaseModel):
    """Issued token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserProfile(BaseModel):
    """Public user profile (no password hash, masked API key)."""

    user_id: str
    email: str
    llm_provider: str
    llm_model: str
    llm_api_key: str  # masked
    llm_api_base: str | None
    telegram_bot_token: str
    telegram_webhook_url: str
    enable_cover_letter: bool
    enable_outreach_message: bool
    ui_language: str
    content_language: str
    default_prompt_id: str
    created_at: str


class UpdateProfileRequest(BaseModel):
    """Partial update to user settings — all fields optional."""

    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_api_base: str | None = None
    telegram_bot_token: str | None = None
    telegram_webhook_secret: str | None = None
    telegram_webhook_url: str | None = None
    enable_cover_letter: bool | None = None
    enable_outreach_message: bool | None = None
    ui_language: str | None = None
    content_language: str | None = None
    default_prompt_id: str | None = None
