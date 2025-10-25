"""Processing service for managing chapter editing jobs."""
import asyncio
from typing import Dict, List, Optional, Callable
from datetime import datetime
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models import Chapter, Project, ProcessingJob
from app.models.database import async_session_maker
from app.services.llm_service import LLMService, SystemPrompts
from app.services.edit_parser import EditParser
from app.services.token_service import TokenService
from app.utils import FileManager, decrypt_api_key

logger = logging.getLogger(__name__)


class ProcessingService:
    """Service for processing chapters with LLM."""

    def __init__(
        self,
        db_session: AsyncSession,
        project_id: int,
        websocket_callback: Optional[Callable] = None,
    ):
        """
        Initialize processing service.

        Args:
            db_session: Database session
            project_id: Project ID to process
            websocket_callback: Optional callback for WebSocket updates
        """
        self.db_session = db_session
        self.project_id = project_id
        self.websocket_callback = websocket_callback
        self.is_running = False
        self.is_paused = False

    async def start_processing(
        self,
        start_chapter: int,
        end_chapter: int,
        worker_count: int = 3,
    ) -> ProcessingJob:
        """
        Start processing chapters.

        Args:
            start_chapter: Starting chapter number
            end_chapter: Ending chapter number
            worker_count: Number of parallel workers

        Returns:
            ProcessingJob instance
        """
        # Create processing job
        job = ProcessingJob(
            project_id=self.project_id,
            start_chapter=start_chapter,
            end_chapter=end_chapter,
            worker_count=worker_count,
            status="running",
        )

        self.db_session.add(job)
        await self.db_session.commit()
        await self.db_session.refresh(job)

        # Update project status
        await self.db_session.execute(
            update(Project)
            .where(Project.id == self.project_id)
            .values(processing_status="processing")
        )
        await self.db_session.commit()

        # Start processing in background
        self.is_running = True
        asyncio.create_task(
            self._process_chapters(job.id, start_chapter, end_chapter, worker_count)
        )

        return job

    async def pause_processing(self):
        """Pause processing."""
        self.is_paused = True

        # Update project status
        await self.db_session.execute(
            update(Project)
            .where(Project.id == self.project_id)
            .values(processing_status="paused")
        )
        await self.db_session.commit()

    async def resume_processing(self):
        """Resume processing."""
        self.is_paused = False

        # Update project status
        await self.db_session.execute(
            update(Project)
            .where(Project.id == self.project_id)
            .values(processing_status="processing")
        )
        await self.db_session.commit()

    async def stop_processing(self):
        """Stop processing."""
        self.is_running = False
        self.is_paused = False

        # Update project status
        await self.db_session.execute(
            update(Project)
            .where(Project.id == self.project_id)
            .values(processing_status="idle")
        )
        await self.db_session.commit()

    async def _process_chapters(
        self,
        job_id: int,
        start_chapter: int,
        end_chapter: int,
        worker_count: int,
    ):
        """
        Process chapters in parallel.

        Args:
            job_id: Processing job ID
            start_chapter: Starting chapter number
            end_chapter: Ending chapter number
            worker_count: Number of parallel workers
        """
        try:
            # Get project and LLM settings
            result = await self.db_session.execute(
                select(Project).where(Project.id == self.project_id)
            )
            project = result.scalar_one_or_none()

            if not project or not project.llm_settings:
                raise ValueError("Project or LLM settings not found")

            # Extract LLM settings
            llm_settings = project.llm_settings
            api_endpoint = llm_settings.get("api_endpoint")
            encrypted_api_key = llm_settings.get("encrypted_api_key")
            model = llm_settings.get("model", "gpt-4")
            temperature = llm_settings.get("temperature", 0.3)
            max_tokens = llm_settings.get("max_tokens", 4096)
            system_prompt = llm_settings.get("system_prompt", SystemPrompts.DEFAULT)

            # Decrypt API key
            api_key = decrypt_api_key(encrypted_api_key)

            # Create LLM service
            llm_service = LLMService(api_endpoint, api_key, model, temperature)

            # Get chapters to process
            result = await self.db_session.execute(
                select(Chapter)
                .where(Chapter.project_id == self.project_id)
                .where(Chapter.chapter_number >= start_chapter)
                .where(Chapter.chapter_number <= end_chapter)
                .where(Chapter.processing_status.in_(["not_started", "failed"]))
                .order_by(Chapter.chapter_number)
            )
            chapters = result.scalars().all()

            if not chapters:
                logger.info("No chapters to process")
                return

            # Create queue
            queue = asyncio.Queue()
            for chapter in chapters:
                await queue.put(chapter)

            # Create semaphore for limiting concurrent workers
            semaphore = asyncio.Semaphore(worker_count)

            # Create worker tasks
            workers = [
                asyncio.create_task(
                    self._worker(
                        worker_id=i,
                        queue=queue,
                        semaphore=semaphore,
                        llm_service=llm_service,
                        system_prompt=system_prompt,
                        max_tokens=max_tokens,
                    )
                )
                for i in range(worker_count)
            ]

            # Wait for all workers to complete
            await queue.join()

            # Cancel workers
            for worker in workers:
                worker.cancel()

            # Wait for workers to finish
            await asyncio.gather(*workers, return_exceptions=True)

            # Update job status
            await self.db_session.execute(
                update(ProcessingJob)
                .where(ProcessingJob.id == job_id)
                .values(status="completed", completed_at=datetime.now())
            )

            # Update project status
            await self.db_session.execute(
                update(Project)
                .where(Project.id == self.project_id)
                .values(processing_status="completed")
            )

            await self.db_session.commit()

            # Send WebSocket update
            if self.websocket_callback:
                await self.websocket_callback(
                    {
                        "type": "processing_complete",
                        "project_id": self.project_id,
                        "message": "All chapters processed successfully",
                    }
                )

        except Exception as e:
            logger.error(f"Error in processing: {e}")

            # Update job status
            await self.db_session.execute(
                update(ProcessingJob)
                .where(ProcessingJob.id == job_id)
                .values(status="failed", error_message=str(e))
            )

            # Update project status
            await self.db_session.execute(
                update(Project)
                .where(Project.id == self.project_id)
                .values(processing_status="idle")
            )

            await self.db_session.commit()

            # Send WebSocket update
            if self.websocket_callback:
                await self.websocket_callback(
                    {
                        "type": "error",
                        "project_id": self.project_id,
                        "message": f"Processing failed: {str(e)}",
                    }
                )

        finally:
            self.is_running = False

    async def _worker(
        self,
        worker_id: int,
        queue: asyncio.Queue,
        semaphore: asyncio.Semaphore,
        llm_service: LLMService,
        system_prompt: str,
        max_tokens: int,
    ):
        """
        Worker task for processing chapters.

        Args:
            worker_id: Worker ID
            queue: Chapter queue
            semaphore: Semaphore for limiting concurrency
            llm_service: LLM service instance
            system_prompt: System prompt for editing
            max_tokens: Maximum tokens per request
        """
        # Create worker's own database session
        async with async_session_maker() as worker_session:
            while True:
                try:
                    # Get chapter from queue (non-blocking)
                    try:
                        chapter = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                    # Wait if paused
                    while self.is_paused and self.is_running:
                        await asyncio.sleep(1)

                    # Check if we should stop
                    if not self.is_running:
                        queue.task_done()
                        break

                    # Acquire semaphore
                    async with semaphore:
                        await self._process_chapter(
                            chapter, worker_session, llm_service, system_prompt, max_tokens
                        )

                    # Mark task as done
                    queue.task_done()

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Worker {worker_id} error: {e}")
                    queue.task_done()

    async def _process_chapter(
        self,
        chapter: Chapter,
        session: AsyncSession,
        llm_service: LLMService,
        system_prompt: str,
        max_tokens: int,
    ):
        """
        Process a single chapter.

        Args:
            chapter: Chapter instance
            session: Database session for this worker
            llm_service: LLM service
            system_prompt: System prompt
            max_tokens: Maximum tokens
        """
        try:
            # Refresh chapter in this session and update status
            await session.merge(chapter)
            chapter.processing_status = "in_progress"
            await session.commit()

            # Send WebSocket update
            if self.websocket_callback:
                await self.websocket_callback(
                    {
                        "type": "chapter_started",
                        "project_id": self.project_id,
                        "chapter_id": chapter.id,
                        "chapter_number": chapter.chapter_number,
                    }
                )

            # Load chapter content
            content = FileManager.load_chapter_content(chapter.original_content_path)

            # Edit chapter with LLM
            result = await llm_service.edit_chapter(content, system_prompt, max_tokens)

            # Parse edits
            commands = EditParser.parse_edits(result["edits"])

            # Apply edits
            edited_content, stats = EditParser.apply_edits(content, commands)

            # Save edits
            edit_data = {
                "original_content": content,
                "edited_content": edited_content,
                "edit_commands": result["edits"],
                "stats": stats,
                "usage": result["usage"],
                "model": result["model"],
                "processed_at": datetime.now().isoformat(),
            }

            edits_path = FileManager.save_chapter_edits(
                self.project_id, chapter.chapter_number, edit_data
            )

            # Update chapter
            chapter.edited_content_path = edits_path
            chapter.processing_status = "completed"
            chapter.processed_at = datetime.now()

            await session.commit()

            # Send WebSocket update
            if self.websocket_callback:
                await self.websocket_callback(
                    {
                        "type": "chapter_completed",
                        "project_id": self.project_id,
                        "chapter_id": chapter.id,
                        "chapter_number": chapter.chapter_number,
                        "stats": stats,
                    }
                )

        except Exception as e:
            logger.error(f"Error processing chapter {chapter.id}: {e}")

            # Update chapter status
            chapter.processing_status = "failed"
            chapter.error_message = str(e)
            await session.commit()

            # Send WebSocket update
            if self.websocket_callback:
                await self.websocket_callback(
                    {
                        "type": "chapter_failed",
                        "project_id": self.project_id,
                        "chapter_id": chapter.id,
                        "chapter_number": chapter.chapter_number,
                        "error": str(e),
                    }
                )
