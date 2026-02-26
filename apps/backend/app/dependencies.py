"""FastAPI dependencies for authentication."""

import logging
from typing import Any

from fastapi import Header, HTTPException

from app.auth import decode_token
from app.database import db
from app.llm import LLMConfig, set_request_llm_config

logger = logging.getLogger(__name__)


async def get_current_user(authorization: str = Header(...)) -> dict[str, Any]:
    """Extract the authenticated user from the Bearer token.

    Sets the per-request LLM config from the user's stored settings so all
    downstream LLM calls automatically use the correct provider/key.

    Returns:
        The full user document from the database.

    Raises:
        HTTPException(401): If token is missing, invalid, or user not found.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]
    payload = decode_token(token, expected_type="access")

    user_id: str = payload.get("sub", "")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Set per-request LLM config so all service calls use this user's provider/key
    set_request_llm_config(
        LLMConfig(
            provider=user.get("llm_provider", "openai"),
            model=user.get("llm_model", ""),
            api_key=user.get("llm_api_key", ""),
            api_base=user.get("llm_api_base"),
        )
    )

    return user
