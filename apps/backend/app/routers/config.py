"""LLM configuration endpoints (per-user settings)."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.database import db
from app.dependencies import get_current_user
from app.llm import check_llm_health, LLMConfig
from app.schemas import (
    LLMConfigRequest,
    LLMConfigResponse,
    FeatureConfigRequest,
    FeatureConfigResponse,
    LanguageConfigRequest,
    LanguageConfigResponse,
    PromptConfigRequest,
    PromptConfigResponse,
    PromptOption,
    ResetDatabaseRequest,
)
from app.prompts import DEFAULT_IMPROVE_PROMPT_ID, IMPROVE_PROMPT_OPTIONS

router = APIRouter(prefix="/config", tags=["Configuration"])


def _mask_api_key(key: str) -> str:
    """Mask API key for display."""
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def _get_prompt_options() -> list[PromptOption]:
    """Return available prompt options for resume tailoring."""
    return [PromptOption(**option) for option in IMPROVE_PROMPT_OPTIONS]


async def _log_llm_health_check(config: LLMConfig) -> None:
    """Run a best-effort health check and log outcome without affecting API responses."""
    try:
        health = await check_llm_health(config)
        if not health.get("healthy", False):
            logging.warning(
                "LLM config saved but health check failed",
                extra={"provider": config.provider, "model": config.model},
            )
    except Exception:
        logging.exception(
            "LLM config saved but health check raised exception",
            extra={"provider": config.provider, "model": config.model},
        )


# Supported languages for i18n
SUPPORTED_LANGUAGES = ["en", "es", "zh", "ja", "pt"]


@router.get("/llm-api-key", response_model=LLMConfigResponse)
async def get_llm_config_endpoint(
    current_user: dict = Depends(get_current_user),
) -> LLMConfigResponse:
    """Get current LLM configuration (API key masked)."""
    return LLMConfigResponse(
        provider=current_user.get("llm_provider", "openai"),
        model=current_user.get("llm_model", ""),
        api_key=_mask_api_key(current_user.get("llm_api_key", "")),
        api_base=current_user.get("llm_api_base"),
    )


@router.put("/llm-api-key", response_model=LLMConfigResponse)
async def update_llm_config(
    request: LLMConfigRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
) -> LLMConfigResponse:
    """Update LLM configuration.

    Saves the configuration and returns it (API key masked).

    Note: We intentionally do NOT hard-fail the update based on a live health check.
    Users may configure proxies/aggregators or temporarily unavailable endpoints and
    still need to persist the configuration. Connectivity can be verified via
    `/config/llm-test` and the System Status panel.
    """
    updates: dict = {}
    if request.provider is not None:
        updates["llm_provider"] = request.provider
    if request.model is not None:
        updates["llm_model"] = request.model
    if request.api_key is not None:
        updates["llm_api_key"] = request.api_key
    if request.api_base is not None:
        updates["llm_api_base"] = request.api_base

    if updates:
        current_user = db.update_user(current_user["user_id"], updates)

    test_config = LLMConfig(
        provider=current_user.get("llm_provider", "openai"),
        model=current_user.get("llm_model", ""),
        api_key=current_user.get("llm_api_key", ""),
        api_base=current_user.get("llm_api_base"),
    )

    background_tasks.add_task(_log_llm_health_check, test_config)

    return LLMConfigResponse(
        provider=test_config.provider,
        model=test_config.model,
        api_key=_mask_api_key(test_config.api_key),
        api_base=test_config.api_base,
    )


@router.post("/llm-test")
async def test_llm_connection(
    request: LLMConfigRequest | None = None,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Test LLM connection with provided or stored configuration.

    If request body is provided, tests with those values (for pre-save testing).
    Otherwise, tests with the currently saved configuration.
    """
    config = LLMConfig(
        provider=(
            request.provider
            if request and request.provider
            else current_user.get("llm_provider", "openai")
        ),
        model=(
            request.model
            if request and request.model
            else current_user.get("llm_model", "")
        ),
        api_key=(
            request.api_key
            if request and request.api_key
            else current_user.get("llm_api_key", "")
        ),
        api_base=(
            request.api_base
            if request and request.api_base is not None
            else current_user.get("llm_api_base")
        ),
    )

    return await check_llm_health(config, include_details=True, test_prompt="Hi")


@router.get("/features", response_model=FeatureConfigResponse)
async def get_feature_config(
    current_user: dict = Depends(get_current_user),
) -> FeatureConfigResponse:
    """Get current feature configuration."""
    return FeatureConfigResponse(
        enable_cover_letter=current_user.get("enable_cover_letter", False),
        enable_outreach_message=current_user.get("enable_outreach_message", False),
    )


@router.put("/features", response_model=FeatureConfigResponse)
async def update_feature_config(
    request: FeatureConfigRequest,
    current_user: dict = Depends(get_current_user),
) -> FeatureConfigResponse:
    """Update feature configuration."""
    updates: dict = {}
    if request.enable_cover_letter is not None:
        updates["enable_cover_letter"] = request.enable_cover_letter
    if request.enable_outreach_message is not None:
        updates["enable_outreach_message"] = request.enable_outreach_message

    if updates:
        current_user = db.update_user(current_user["user_id"], updates)

    return FeatureConfigResponse(
        enable_cover_letter=current_user.get("enable_cover_letter", False),
        enable_outreach_message=current_user.get("enable_outreach_message", False),
    )


@router.get("/language", response_model=LanguageConfigResponse)
async def get_language_config(
    current_user: dict = Depends(get_current_user),
) -> LanguageConfigResponse:
    """Get current language configuration."""
    return LanguageConfigResponse(
        ui_language=current_user.get("ui_language", "en"),
        content_language=current_user.get("content_language", "en"),
        supported_languages=SUPPORTED_LANGUAGES,
    )


@router.put("/language", response_model=LanguageConfigResponse)
async def update_language_config(
    request: LanguageConfigRequest,
    current_user: dict = Depends(get_current_user),
) -> LanguageConfigResponse:
    """Update language configuration."""
    updates: dict = {}

    if request.ui_language is not None:
        if request.ui_language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported UI language: {request.ui_language}. Supported: {SUPPORTED_LANGUAGES}",
            )
        updates["ui_language"] = request.ui_language

    if request.content_language is not None:
        if request.content_language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported content language: {request.content_language}. Supported: {SUPPORTED_LANGUAGES}",
            )
        updates["content_language"] = request.content_language

    if updates:
        current_user = db.update_user(current_user["user_id"], updates)

    return LanguageConfigResponse(
        ui_language=current_user.get("ui_language", "en"),
        content_language=current_user.get("content_language", "en"),
        supported_languages=SUPPORTED_LANGUAGES,
    )


@router.get("/prompts", response_model=PromptConfigResponse)
async def get_prompt_config(
    current_user: dict = Depends(get_current_user),
) -> PromptConfigResponse:
    """Get current prompt configuration for resume tailoring."""
    options = _get_prompt_options()
    option_ids = {option.id for option in options}
    default_prompt_id = current_user.get("default_prompt_id", DEFAULT_IMPROVE_PROMPT_ID)
    if default_prompt_id not in option_ids:
        default_prompt_id = DEFAULT_IMPROVE_PROMPT_ID

    return PromptConfigResponse(
        default_prompt_id=default_prompt_id,
        prompt_options=options,
    )


@router.put("/prompts", response_model=PromptConfigResponse)
async def update_prompt_config(
    request: PromptConfigRequest,
    current_user: dict = Depends(get_current_user),
) -> PromptConfigResponse:
    """Update prompt configuration for resume tailoring."""
    options = _get_prompt_options()
    option_ids = {option.id for option in options}

    if request.default_prompt_id is not None:
        if request.default_prompt_id not in option_ids:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Unsupported prompt id: "
                    f"{request.default_prompt_id}. Supported: {sorted(option_ids)}"
                ),
            )
        current_user = db.update_user(
            current_user["user_id"], {"default_prompt_id": request.default_prompt_id}
        )

    default_prompt_id = current_user.get("default_prompt_id", DEFAULT_IMPROVE_PROMPT_ID)
    if default_prompt_id not in option_ids:
        default_prompt_id = DEFAULT_IMPROVE_PROMPT_ID

    return PromptConfigResponse(
        default_prompt_id=default_prompt_id,
        prompt_options=options,
    )


@router.post("/reset")
async def reset_database_endpoint(
    request: ResetDatabaseRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Reset the database and clear all data for the current user.

    WARNING: This action is irreversible. It will:
    1. Delete all resumes, jobs, and improvements for this user
    2. Delete all uploaded files for this user

    Requires confirmation token for safety.
    """
    if request.confirm != "RESET_ALL_DATA":
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Pass confirm=RESET_ALL_DATA in request body.",
        )
    db.reset_database(current_user["user_id"])
    return {"message": "All your data has been reset successfully"}
