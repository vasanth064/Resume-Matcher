"""Authentication endpoints: signup, login, token refresh, profile."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.database import db
from app.dependencies import get_current_user
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserProfile,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

SUPPORTED_LANGUAGES = ["en", "es", "zh", "ja", "pt"]


def _mask_api_key(key: str) -> str:
    """Return a masked version of an API key for display."""
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def _user_to_profile(user: dict) -> UserProfile:
    """Convert a user document to the public profile schema."""
    return UserProfile(
        user_id=user["user_id"],
        email=user["email"],
        llm_provider=user.get("llm_provider", "openai"),
        llm_model=user.get("llm_model", ""),
        llm_api_key=_mask_api_key(user.get("llm_api_key", "")),
        llm_api_base=user.get("llm_api_base"),
        telegram_bot_token=user.get("telegram_bot_token", ""),
        telegram_webhook_url=user.get("telegram_webhook_url", ""),
        enable_cover_letter=user.get("enable_cover_letter", False),
        enable_outreach_message=user.get("enable_outreach_message", False),
        ui_language=user.get("ui_language", "en"),
        content_language=user.get("content_language", "en"),
        default_prompt_id=user.get("default_prompt_id", "default"),
        created_at=user.get("created_at", ""),
    )


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(request: SignupRequest) -> TokenResponse:
    """Register a new user account.

    Creates the user with their LLM and (optional) Telegram settings,
    then returns a token pair so they are immediately logged in.
    """
    # Check for duplicate email
    existing = db.get_user_by_email(request.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    password_hash = hash_password(request.password)

    user = db.create_user(
        email=request.email,
        password_hash=password_hash,
        llm_provider=request.llm_provider,
        llm_model=request.llm_model,
        llm_api_key=request.llm_api_key,
        llm_api_base=request.llm_api_base,
        telegram_bot_token=request.telegram_bot_token,
        telegram_webhook_secret=request.telegram_webhook_secret,
        telegram_webhook_url=request.telegram_webhook_url,
    )

    return TokenResponse(
        access_token=create_access_token(user["user_id"]),
        refresh_token=create_refresh_token(user["user_id"]),
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest) -> TokenResponse:
    """Authenticate with email and password, receive a token pair."""
    user = db.get_user_by_email(request.email)
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    return TokenResponse(
        access_token=create_access_token(user["user_id"]),
        refresh_token=create_refresh_token(user["user_id"]),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest) -> TokenResponse:
    """Exchange a refresh token for a new access token."""
    payload = decode_token(request.refresh_token, expected_type="refresh")

    user_id: str = payload.get("sub", "")
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.get("/me", response_model=UserProfile)
async def get_me(current_user: dict = Depends(get_current_user)) -> UserProfile:
    """Return the authenticated user's profile."""
    return _user_to_profile(current_user)


@router.put("/me", response_model=UserProfile)
async def update_me(
    request: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user),
) -> UserProfile:
    """Update the authenticated user's settings.

    All fields are optional — only provided fields are updated.
    """
    if request.ui_language is not None and request.ui_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported UI language: {request.ui_language}",
        )
    if request.content_language is not None and request.content_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content language: {request.content_language}",
        )

    updates = {
        k: v
        for k, v in request.model_dump().items()
        if v is not None
    }

    if not updates:
        return _user_to_profile(current_user)

    updated_user = db.update_user(current_user["user_id"], updates)
    return _user_to_profile(updated_user)
