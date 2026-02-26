"""TinyDB database layer for JSON storage."""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from tinydb import Query, TinyDB
from tinydb.table import Table

from app.config import settings

logger = logging.getLogger(__name__)


class Database:
    """TinyDB wrapper for resume matcher data."""

    _master_resume_lock = asyncio.Lock()

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db: TinyDB | None = None

    @property
    def db(self) -> TinyDB:
        """Lazy initialization of TinyDB instance."""
        if self._db is None:
            self._db = TinyDB(self.db_path)
        return self._db

    @property
    def users(self) -> Table:
        """Users table."""
        return self.db.table("users")

    @property
    def resumes(self) -> Table:
        """Resumes table."""
        return self.db.table("resumes")

    @property
    def jobs(self) -> Table:
        """Job descriptions table."""
        return self.db.table("jobs")

    @property
    def improvements(self) -> Table:
        """Improvement results table."""
        return self.db.table("improvements")

    def close(self) -> None:
        """Close database connection."""
        if self._db is not None:
            self._db.close()
            self._db = None

    # -------------------------------------------------------------------------
    # User operations
    # -------------------------------------------------------------------------

    def create_user(
        self,
        email: str,
        password_hash: str,
        llm_provider: str = "openai",
        llm_model: str = "",
        llm_api_key: str = "",
        llm_api_base: str | None = None,
        telegram_bot_token: str = "",
        telegram_webhook_secret: str = "",
        telegram_webhook_url: str = "",
    ) -> dict[str, Any]:
        """Create a new user account."""
        user_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        doc: dict[str, Any] = {
            "user_id": user_id,
            "email": email.lower().strip(),
            "password_hash": password_hash,
            "created_at": now,
            "updated_at": now,
            # LLM settings
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "llm_api_key": llm_api_key,
            "llm_api_base": llm_api_base,
            # Telegram settings
            "telegram_bot_token": telegram_bot_token,
            "telegram_webhook_secret": telegram_webhook_secret,
            "telegram_webhook_url": telegram_webhook_url,
            # Feature flags
            "enable_cover_letter": False,
            "enable_outreach_message": False,
            # Language settings
            "ui_language": "en",
            "content_language": "en",
            # Prompt config
            "default_prompt_id": "default",
        }
        self.users.insert(doc)
        return doc

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        """Get user by ID."""
        User = Query()
        result = self.users.search(User.user_id == user_id)
        return result[0] if result else None

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Get user by email (case-insensitive)."""
        User = Query()
        result = self.users.search(User.email == email.lower().strip())
        return result[0] if result else None

    def update_user(self, user_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update user by ID.

        Raises:
            ValueError: If user not found.
        """
        User = Query()
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        updated_count = self.users.update(updates, User.user_id == user_id)

        if not updated_count:
            raise ValueError(f"User not found: {user_id}")

        result = self.get_user(user_id)
        if not result:
            raise ValueError(f"User disappeared after update: {user_id}")
        return result

    # -------------------------------------------------------------------------
    # Resume operations (all scoped to user_id)
    # -------------------------------------------------------------------------

    def create_resume(
        self,
        content: str,
        user_id: str,
        content_type: str = "md",
        filename: str | None = None,
        is_master: bool = False,
        parent_id: str | None = None,
        processed_data: dict[str, Any] | None = None,
        processing_status: str = "pending",
        cover_letter: str | None = None,
        outreach_message: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Create a new resume entry.

        processing_status: "pending", "processing", "ready", "failed"
        """
        resume_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        doc = {
            "resume_id": resume_id,
            "user_id": user_id,
            "content": content,
            "content_type": content_type,
            "filename": filename,
            "is_master": is_master,
            "parent_id": parent_id,
            "processed_data": processed_data,
            "processing_status": processing_status,
            "cover_letter": cover_letter,
            "outreach_message": outreach_message,
            "title": title,
            "created_at": now,
            "updated_at": now,
        }
        self.resumes.insert(doc)
        return doc

    async def create_resume_atomic_master(
        self,
        content: str,
        user_id: str,
        content_type: str = "md",
        filename: str | None = None,
        processed_data: dict[str, Any] | None = None,
        processing_status: str = "pending",
        cover_letter: str | None = None,
        outreach_message: str | None = None,
    ) -> dict[str, Any]:
        """Create a new resume with atomic master assignment (per-user).

        Uses an asyncio.Lock to prevent race conditions when multiple uploads
        happen concurrently and both try to become master.
        """
        async with self._master_resume_lock:
            current_master = self.get_master_resume(user_id)
            is_master = current_master is None

            # Recovery: if the current master is stuck in failed parsing state,
            # promote the next upload to become the new master resume.
            if current_master and current_master.get("processing_status") == "failed":
                Resume = Query()
                self.resumes.update(
                    {"is_master": False},
                    (Resume.user_id == user_id)
                    & (Resume.resume_id == current_master["resume_id"]),
                )
                is_master = True

            return self.create_resume(
                content=content,
                user_id=user_id,
                content_type=content_type,
                filename=filename,
                is_master=is_master,
                processed_data=processed_data,
                processing_status=processing_status,
                cover_letter=cover_letter,
                outreach_message=outreach_message,
            )

    def get_resume(self, resume_id: str, user_id: str) -> dict[str, Any] | None:
        """Get resume by ID, scoped to user."""
        Resume = Query()
        result = self.resumes.search(
            (Resume.resume_id == resume_id) & (Resume.user_id == user_id)
        )
        return result[0] if result else None

    def get_master_resume(self, user_id: str) -> dict[str, Any] | None:
        """Get the master resume for a user."""
        Resume = Query()
        result = self.resumes.search(
            (Resume.user_id == user_id) & (Resume.is_master == True)
        )
        return result[0] if result else None

    def update_resume(
        self, resume_id: str, updates: dict[str, Any], user_id: str
    ) -> dict[str, Any]:
        """Update resume by ID, scoped to user.

        Raises:
            ValueError: If resume not found or doesn't belong to user.
        """
        Resume = Query()
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        updated_count = self.resumes.update(
            updates,
            (Resume.resume_id == resume_id) & (Resume.user_id == user_id),
        )

        if not updated_count:
            raise ValueError(f"Resume not found: {resume_id}")

        result = self.get_resume(resume_id, user_id)
        if not result:
            raise ValueError(f"Resume disappeared after update: {resume_id}")

        return result

    def delete_resume(self, resume_id: str, user_id: str) -> bool:
        """Delete resume by ID, scoped to user."""
        Resume = Query()
        removed = self.resumes.remove(
            (Resume.resume_id == resume_id) & (Resume.user_id == user_id)
        )
        return len(removed) > 0

    def list_resumes(self, user_id: str) -> list[dict[str, Any]]:
        """List all resumes for a user."""
        Resume = Query()
        return list(self.resumes.search(Resume.user_id == user_id))

    def set_master_resume(self, resume_id: str, user_id: str) -> bool:
        """Set a resume as the master for a user, unsetting any existing master.

        Returns False if the resume doesn't exist or doesn't belong to user.
        """
        Resume = Query()

        target = self.resumes.search(
            (Resume.resume_id == resume_id) & (Resume.user_id == user_id)
        )
        if not target:
            logger.warning("Cannot set master: resume %s not found for user %s", resume_id, user_id)
            return False

        # Unset current master for this user
        self.resumes.update(
            {"is_master": False},
            (Resume.user_id == user_id) & (Resume.is_master == True),
        )
        # Set new master
        updated = self.resumes.update(
            {"is_master": True},
            (Resume.resume_id == resume_id) & (Resume.user_id == user_id),
        )
        return len(updated) > 0

    # -------------------------------------------------------------------------
    # Job operations (scoped to user_id)
    # -------------------------------------------------------------------------

    def create_job(
        self, content: str, user_id: str, resume_id: str | None = None
    ) -> dict[str, Any]:
        """Create a new job description entry."""
        job_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        doc = {
            "job_id": job_id,
            "user_id": user_id,
            "content": content,
            "resume_id": resume_id,
            "created_at": now,
        }
        self.jobs.insert(doc)
        return doc

    def get_job(self, job_id: str, user_id: str) -> dict[str, Any] | None:
        """Get job by ID, scoped to user."""
        Job = Query()
        result = self.jobs.search(
            (Job.job_id == job_id) & (Job.user_id == user_id)
        )
        return result[0] if result else None

    def update_job(
        self, job_id: str, updates: dict[str, Any], user_id: str
    ) -> dict[str, Any] | None:
        """Update a job by ID, scoped to user."""
        Job = Query()
        updated = self.jobs.update(
            updates, (Job.job_id == job_id) & (Job.user_id == user_id)
        )
        if not updated:
            return None
        return self.get_job(job_id, user_id)

    # -------------------------------------------------------------------------
    # Improvement operations (scoped to user_id)
    # -------------------------------------------------------------------------

    def create_improvement(
        self,
        original_resume_id: str,
        tailored_resume_id: str,
        job_id: str,
        improvements: list[dict[str, Any]],
        user_id: str,
    ) -> dict[str, Any]:
        """Create an improvement result entry."""
        request_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        doc = {
            "request_id": request_id,
            "user_id": user_id,
            "original_resume_id": original_resume_id,
            "tailored_resume_id": tailored_resume_id,
            "job_id": job_id,
            "improvements": improvements,
            "created_at": now,
        }
        self.improvements.insert(doc)
        return doc

    def get_improvement_by_tailored_resume(
        self, tailored_resume_id: str, user_id: str
    ) -> dict[str, Any] | None:
        """Get improvement record by tailored resume ID, scoped to user."""
        Improvement = Query()
        result = self.improvements.search(
            (Improvement.tailored_resume_id == tailored_resume_id)
            & (Improvement.user_id == user_id)
        )
        return result[0] if result else None

    # -------------------------------------------------------------------------
    # Stats (per-user)
    # -------------------------------------------------------------------------

    def get_stats(self, user_id: str) -> dict[str, Any]:
        """Get database statistics for a specific user."""
        Resume = Query()
        Job = Query()
        Improvement = Query()
        return {
            "total_resumes": len(self.resumes.search(Resume.user_id == user_id)),
            "total_jobs": len(self.jobs.search(Job.user_id == user_id)),
            "total_improvements": len(
                self.improvements.search(Improvement.user_id == user_id)
            ),
            "has_master_resume": self.get_master_resume(user_id) is not None,
        }

    def reset_database(self, user_id: str) -> None:
        """Delete all data belonging to a user (resumes, jobs, improvements)."""
        Resume = Query()
        Job = Query()
        Improvement = Query()

        self.resumes.remove(Resume.user_id == user_id)
        self.jobs.remove(Job.user_id == user_id)
        self.improvements.remove(Improvement.user_id == user_id)

        # Clear user's uploaded files
        uploads_dir = settings.data_dir / "uploads"
        if uploads_dir.exists():
            import shutil
            user_uploads = uploads_dir / user_id
            if user_uploads.exists():
                shutil.rmtree(user_uploads)


# Global database instance
db = Database()
