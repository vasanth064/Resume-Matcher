"""Telegram webhook router and tailoring orchestration."""

import copy
import json
import logging
from typing import Any

from fastapi import APIRouter, Header, Request, Response

from app.config import settings
from app.database import db
from app.services.telegram import TelegramClient

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Telegram"])

# Module-level client, initialized during app lifespan
_client: TelegramClient | None = None

WELCOME_MESSAGE = (
    "Welcome to Resume Matcher Bot!\n\n"
    "Send me a job description (paste the full text) and I'll:\n"
    "1. Tailor your master resume to match it\n"
    "2. Generate a PDF of the tailored resume\n"
    "3. Write a cover letter\n\n"
    "Just paste a job description to get started."
)

TOO_SHORT_MESSAGE = (
    "That message looks too short to be a job description. "
    "Please paste the full job description text (at least 50 characters)."
)

UNKNOWN_COMMAND_MESSAGE = (
    "I don't recognize that command. "
    "Just paste a job description as plain text and I'll tailor your resume to it."
)

NO_MASTER_RESUME_MESSAGE = (
    "You don't have a master resume set up yet. "
    "Please upload your resume at the Resume Matcher web app first, "
    "then come back and send me a job description."
)

PROCESSING_MESSAGE = "Got it! Tailoring your resume now. This may take a minute..."

ERROR_MESSAGE = "Something went wrong while processing your request. Please try again later."

MIN_JD_LENGTH = 50


def get_client() -> TelegramClient | None:
    """Get the module-level Telegram client."""
    return _client


def set_client(client: TelegramClient | None) -> None:
    """Set the module-level Telegram client."""
    global _client
    _client = client


@router.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(None),
) -> Response:
    """Handle incoming Telegram webhook updates."""
    # Validate secret token if configured
    if settings.telegram_webhook_secret:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            logger.warning("Telegram webhook: invalid secret token")
            return Response(status_code=403)

    client = get_client()
    if not client:
        logger.error("Telegram webhook received but client not initialized")
        return Response(status_code=200)

    try:
        body = await request.json()
    except Exception:
        logger.warning("Telegram webhook: invalid JSON body")
        return Response(status_code=200)

    # Extract message
    message = body.get("message")
    if not message:
        return Response(status_code=200)

    chat_id = message.get("chat", {}).get("id")
    text = (message.get("text") or "").strip()
    if not chat_id or not text:
        return Response(status_code=200)

    # Always respond 200 quickly to Telegram, process in the handler
    try:
        await _handle_message(client, chat_id, text)
    except Exception as e:
        logger.error("Telegram message handler failed: %s", e, exc_info=True)
        try:
            await client.send_message(chat_id, ERROR_MESSAGE)
        except Exception:
            logger.error("Failed to send error message to Telegram")

    return Response(status_code=200)


async def _handle_message(client: TelegramClient, chat_id: int, text: str) -> None:
    """Route incoming message to the appropriate handler."""
    if text == "/start":
        await client.send_message(chat_id, WELCOME_MESSAGE)
        return

    if text.startswith("/"):
        await client.send_message(chat_id, UNKNOWN_COMMAND_MESSAGE)
        return

    if len(text) < MIN_JD_LENGTH:
        await client.send_message(chat_id, TOO_SHORT_MESSAGE)
        return

    # Treat as job description — run the tailoring pipeline
    await _tailor_and_send(client, chat_id, text)


async def _tailor_and_send(client: TelegramClient, chat_id: int, jd_text: str) -> None:
    """Run the full tailoring pipeline and send results back."""
    from app.pdf import render_resume_pdf
    from app.services.cover_letter import (
        generate_cover_letter,
        generate_resume_title,
    )
    from app.services.improver import extract_job_keywords, improve_resume
    from app.services.refiner import (
        RefinementConfig,
        calculate_keyword_match,
        refine_resume,
    )

    # Step 1: Get master resume
    master_resume = db.get_master_resume()
    if not master_resume or not master_resume.get("processed_data"):
        await client.send_message(chat_id, NO_MASTER_RESUME_MESSAGE)
        return

    master_data: dict[str, Any] = master_resume["processed_data"]
    resume_id = master_resume["resume_id"]

    await client.send_message(chat_id, PROCESSING_MESSAGE)

    # Step 2: Create job record
    job = db.create_job(content=jd_text, resume_id=resume_id)
    job_id = job["job_id"]

    # Step 3: Extract keywords
    await client.send_chat_action(chat_id, "typing")
    job_keywords = await extract_job_keywords(jd_text)

    # Step 4: Improve resume
    await client.send_chat_action(chat_id, "typing")
    improved_data = await improve_resume(
        original_resume=master_resume["content"],
        job_description=jd_text,
        job_keywords=job_keywords,
    )

    # Step 5: Preserve personal info from master
    improved_data["personalInfo"] = copy.deepcopy(master_data.get("personalInfo", {}))

    # Step 6: Refine resume
    await client.send_chat_action(chat_id, "typing")
    initial_match = calculate_keyword_match(improved_data, job_keywords)
    refinement_result = await refine_resume(
        initial_tailored=improved_data,
        master_resume=master_data,
        job_description=jd_text,
        job_keywords=job_keywords,
        config=RefinementConfig(),
    )
    improved_data = refinement_result.refined_data
    final_match = refinement_result.final_match_percentage

    # Step 7: Generate title
    await client.send_chat_action(chat_id, "typing")
    title = await generate_resume_title(jd_text)

    # Step 8: Generate cover letter
    await client.send_chat_action(chat_id, "typing")
    cover_letter = await generate_cover_letter(improved_data, jd_text)

    # Step 9: Save to DB
    improved_text = json.dumps(improved_data, indent=2)
    tailored_resume = db.create_resume(
        content=improved_text,
        content_type="json",
        filename=f"telegram_tailored_{job_id}",
        is_master=False,
        parent_id=resume_id,
        processed_data=improved_data,
        processing_status="ready",
        cover_letter=cover_letter,
        title=title,
    )
    tailored_resume_id = tailored_resume["resume_id"]

    from app.services.improver import generate_improvements

    improvements = generate_improvements(job_keywords)
    db.create_improvement(
        original_resume_id=resume_id,
        tailored_resume_id=tailored_resume_id,
        job_id=job_id,
        improvements=improvements,
    )

    # Step 10: Render PDF
    await client.send_chat_action(chat_id, "upload_document")
    print_url = (
        f"{settings.frontend_base_url}/print/resumes/{tailored_resume_id}"
        "?template=swiss-single&pageSize=A4"
    )
    pdf_bytes = await render_resume_pdf(print_url, "A4")

    # Step 11: Send results
    # Build summary caption
    keywords_injected = (
        len(refinement_result.keyword_analysis.injectable_keywords)
        if refinement_result.keyword_analysis
        else 0
    )
    ai_phrases_cleaned = len(refinement_result.ai_phrases_removed)

    caption = (
        f"{title}\n\n"
        f"Keyword match: {initial_match:.0f}% → {final_match:.0f}%\n"
        f"Refinement passes: {refinement_result.passes_completed}\n"
        f"Keywords injected: {keywords_injected}\n"
        f"AI phrases cleaned: {ai_phrases_cleaned}"
    )

    pdf_filename = f"{title}.pdf" if title else "tailored_resume.pdf"
    # Sanitize filename
    pdf_filename = "".join(c for c in pdf_filename if c.isalnum() or c in " ._-@").strip()
    if not pdf_filename.endswith(".pdf"):
        pdf_filename += ".pdf"

    await client.send_document(chat_id, pdf_bytes, pdf_filename, caption=caption)

    # Send cover letter as separate message (can exceed caption limit)
    if cover_letter:
        await client.send_message(chat_id, f"--- Cover Letter ---\n\n{cover_letter}")
