"""Lightweight Telegram Bot API client using httpx."""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Telegram API limits
MAX_MESSAGE_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024


class TelegramClient:
    """Async wrapper around the Telegram Bot API."""

    def __init__(self, token: str) -> None:
        self._base_url = f"https://api.telegram.org/bot{token}"
        self._client = httpx.AsyncClient(timeout=30.0)

    async def send_message(self, chat_id: int, text: str) -> dict[str, Any]:
        """Send a text message, truncating at the Telegram limit."""
        if len(text) > MAX_MESSAGE_LENGTH:
            text = text[: MAX_MESSAGE_LENGTH - 3] + "..."
        return await self._post("sendMessage", {"chat_id": chat_id, "text": text})

    async def send_document(
        self,
        chat_id: int,
        document_bytes: bytes,
        filename: str,
        caption: str | None = None,
    ) -> dict[str, Any]:
        """Send a file as a document attachment."""
        data: dict[str, Any] = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption[:MAX_CAPTION_LENGTH]
        files = {"document": (filename, document_bytes, "application/pdf")}
        return await self._post("sendDocument", data, files=files)

    async def send_chat_action(self, chat_id: int, action: str = "typing") -> dict[str, Any]:
        """Show a chat action indicator (e.g. 'typing...')."""
        return await self._post("sendChatAction", {"chat_id": chat_id, "action": action})

    async def set_webhook(self, url: str, secret_token: str | None = None) -> dict[str, Any]:
        """Register the webhook URL with Telegram."""
        payload: dict[str, Any] = {"url": url}
        if secret_token:
            payload["secret_token"] = secret_token
        return await self._post("setWebhook", payload)

    async def delete_webhook(self) -> dict[str, Any]:
        """Remove the registered webhook."""
        return await self._post("deleteWebhook", {})

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def _post(
        self,
        method: str,
        data: dict[str, Any],
        files: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a POST request to the Telegram Bot API."""
        url = f"{self._base_url}/{method}"
        try:
            if files:
                response = await self._client.post(url, data=data, files=files)
            else:
                response = await self._client.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error("Telegram API error on %s: %s %s", method, e.response.status_code, e.response.text)
            raise
        except httpx.RequestError as e:
            logger.error("Telegram API request failed on %s: %s", method, e)
            raise
