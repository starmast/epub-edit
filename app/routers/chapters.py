"""Chapter management API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel

from app.models import get_db, Chapter
from app.utils import FileManager

router = APIRouter()


# Pydantic models
class ChapterResponse(BaseModel):
    id: int
    project_id: int
    chapter_number: int
    title: Optional[str]
    processing_status: str
    token_count: int
    word_count: int
    error_message: Optional[str]
    processed_at: Optional[str]

    class Config:
        from_attributes = True


class ChapterContent(BaseModel):
    content: str


class ChapterDiff(BaseModel):
    original_lines: List[str]
    edited_lines: List[str]
    stats: Optional[dict]
    chapter_number: int
    title: Optional[str]


@router.get("/projects/{project_id}/chapters", response_model=List[ChapterResponse])
async def list_chapters(project_id: int, db: AsyncSession = Depends(get_db)):
    """
    List all chapters for a project.
    """
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.chapter_number)
    )
    chapters = result.scalars().all()

    return [
        ChapterResponse(
            id=chapter.id,
            project_id=chapter.project_id,
            chapter_number=chapter.chapter_number,
            title=chapter.title,
            processing_status=chapter.processing_status,
            token_count=chapter.token_count,
            word_count=chapter.word_count,
            error_message=chapter.error_message,
            processed_at=chapter.processed_at.isoformat()
            if chapter.processed_at
            else None,
        )
        for chapter in chapters
    ]


@router.get("/chapters/{chapter_id}")
async def get_chapter(chapter_id: int, db: AsyncSession = Depends(get_db)):
    """
    Get a specific chapter.
    """
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()

    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    return ChapterResponse(
        id=chapter.id,
        project_id=chapter.project_id,
        chapter_number=chapter.chapter_number,
        title=chapter.title,
        processing_status=chapter.processing_status,
        token_count=chapter.token_count,
        word_count=chapter.word_count,
        error_message=chapter.error_message,
        processed_at=chapter.processed_at.isoformat() if chapter.processed_at else None,
    )


@router.get("/chapters/{chapter_id}/content")
async def get_chapter_content(chapter_id: int, db: AsyncSession = Depends(get_db)):
    """
    Get the original content of a chapter.
    """
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()

    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    try:
        content = FileManager.load_chapter_content(chapter.original_content_path)
        return {"content": content, "chapter_number": chapter.chapter_number, "title": chapter.title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load content: {str(e)}")


@router.get("/chapters/{chapter_id}/diff")
async def get_chapter_diff(chapter_id: int, db: AsyncSession = Depends(get_db)):
    """
    Get the diff view for a chapter (original vs edited).
    Returns line-by-line comparison for better diff viewing.
    """
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()

    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    if chapter.processing_status not in ["completed", "in_progress"]:
        raise HTTPException(status_code=400, detail="Chapter has not been processed yet")

    try:
        # Load edit data
        edit_data = FileManager.load_chapter_edits(
            chapter.project_id, chapter.chapter_number
        )

        if not edit_data:
            raise HTTPException(status_code=404, detail="Edit data not found")

        if "original_lines" not in edit_data or "edited_lines" not in edit_data:
            raise HTTPException(status_code=400, detail="Edit data format invalid - please reprocess this chapter")

        return {
            "original_lines": edit_data["original_lines"],
            "edited_lines": edit_data["edited_lines"],
            "stats": edit_data.get("stats", {}),
            "chapter_number": chapter.chapter_number,
            "title": chapter.title,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate diff: {str(e)}")


@router.patch("/chapters/{chapter_id}/edits")
async def update_chapter_edits(
    chapter_id: int,
    edited_content: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually update/override edits for a chapter.
    """
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()

    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    try:
        from app.services.processing_service import ProcessingService

        # Load existing edit data or create new
        edit_data = FileManager.load_chapter_edits(
            chapter.project_id, chapter.chapter_number
        ) or {}

        # Load original XHTML
        original_xhtml = FileManager.load_chapter_content(
            chapter.original_content_path
        )

        # Extract original text (already filters blank lines)
        original_text = ProcessingService._extract_body_content(original_xhtml)

        # Split into lines (no filtering needed, already done in extraction)
        original_lines = original_text.split('\n')
        edited_lines = edited_content.split('\n')

        # Update with new line-based format
        edit_data["original_xhtml"] = original_xhtml
        edit_data["original_lines"] = original_lines
        edit_data["edited_lines"] = edited_lines
        edit_data["manually_edited"] = True

        # Calculate basic stats
        edit_data["stats"] = {
            "total_edits": 0,
            "manually_edited": True,
            "original_line_count": len(edit_data["original_lines"]),
            "edited_line_count": len(edit_data["edited_lines"]),
        }

        # Save updated edit data
        FileManager.save_chapter_edits(
            chapter.project_id, chapter.chapter_number, edit_data
        )

        return {"message": "Chapter edits updated successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update edits: {str(e)}")


@router.post("/chapters/{chapter_id}/retry")
async def retry_chapter(chapter_id: int, db: AsyncSession = Depends(get_db)):
    """
    Reset a chapter's status to retry processing.
    """
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()

    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    # Reset status
    chapter.processing_status = "not_started"
    chapter.error_message = None
    chapter.processed_at = None

    await db.commit()

    return {"message": "Chapter reset for retry"}
