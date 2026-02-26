"""FastAPI application entry point."""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

# Fix for Windows: Use ProactorEventLoop for subprocess support (Playwright)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import settings
from app.database import db
from app.pdf import close_pdf_renderer, init_pdf_renderer
from app.routers import config_router, enrichment_router, health_router, jobs_router, resumes_router, telegram_router
from app.routers.telegram import get_client as get_telegram_client, set_client as set_telegram_client
from app.services.telegram import TelegramClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    # PDF renderer uses lazy initialization - will initialize on first use
    # await init_pdf_renderer()

    # Telegram bot setup (only if token is configured)
    if settings.telegram_bot_token:
        try:
            tg = TelegramClient(settings.telegram_bot_token)
            set_telegram_client(tg)
            if settings.telegram_webhook_url:
                webhook_url = f"{settings.telegram_webhook_url.rstrip('/')}/webhook/telegram"
                await tg.set_webhook(webhook_url, settings.telegram_webhook_secret or None)
                logger.info("Telegram webhook registered: %s", webhook_url)
        except Exception as e:
            logger.error("Failed to initialize Telegram bot: %s", e)

    yield
    # Shutdown - wrap each cleanup in try-except to ensure all resources are released
    try:
        await close_pdf_renderer()
    except Exception as e:
        logger.error(f"Error closing PDF renderer: {e}")

    try:
        tg_client = get_telegram_client()
        if tg_client:
            await tg_client.close()
            set_telegram_client(None)
    except Exception as e:
        logger.error(f"Error closing Telegram client: {e}")

    try:
        db.close()
    except Exception as e:
        logger.error(f"Error closing database: {e}")


app = FastAPI(
    title="Resume Matcher API",
    description="AI-powered resume tailoring for job descriptions",
    version=__version__,
    lifespan=lifespan,
)

# CORS middleware - origins configurable via CORS_ORIGINS env var
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix="/api/v1")
app.include_router(config_router, prefix="/api/v1")
app.include_router(resumes_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(enrichment_router, prefix="/api/v1")
app.include_router(telegram_router)  # Webhook at /webhook/telegram (no API prefix)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Resume Matcher API",
        "version": __version__,
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
