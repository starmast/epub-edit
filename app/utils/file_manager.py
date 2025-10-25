"""File system management utilities."""
import os
import shutil
from pathlib import Path
from typing import Optional
from app.config import settings
import json


class FileManager:
    """Manages file operations for projects and chapters."""

    @staticmethod
    def get_project_dir(project_id: int) -> Path:
        """Get the base directory for a project."""
        project_dir = Path(settings.projects_dir) / str(project_id)
        return project_dir

    @staticmethod
    def create_project_structure(project_id: int) -> dict:
        """
        Create the directory structure for a new project.

        Returns:
            Dictionary with paths to different directories
        """
        base_dir = FileManager.get_project_dir(project_id)

        dirs = {
            "base": base_dir,
            "original": base_dir / "original",
            "chapters": base_dir / "original" / "chapters",
            "edits": base_dir / "edits",
            "output": base_dir / "output",
        }

        for directory in dirs.values():
            directory.mkdir(parents=True, exist_ok=True)

        return {k: str(v) for k, v in dirs.items()}

    @staticmethod
    def save_epub(project_id: int, file_content: bytes, filename: str) -> str:
        """
        Save uploaded ePub file.

        Args:
            project_id: Project ID
            file_content: File content as bytes
            filename: Original filename

        Returns:
            Path where file was saved
        """
        dirs = FileManager.create_project_structure(project_id)
        epub_path = Path(dirs["original"]) / filename

        with open(epub_path, "wb") as f:
            f.write(file_content)

        return str(epub_path)

    @staticmethod
    def save_chapter_content(
        project_id: int, chapter_number: int, content: str
    ) -> str:
        """
        Save chapter content to file.

        Args:
            project_id: Project ID
            chapter_number: Chapter number
            content: HTML/text content

        Returns:
            Path where chapter was saved
        """
        dirs = FileManager.create_project_structure(project_id)
        chapter_path = (
            Path(dirs["chapters"]) / f"chapter_{chapter_number:03d}.html"
        )

        with open(chapter_path, "w", encoding="utf-8") as f:
            f.write(content)

        return str(chapter_path)

    @staticmethod
    def load_chapter_content(chapter_path: str) -> str:
        """
        Load chapter content from file.

        Args:
            chapter_path: Path to chapter file

        Returns:
            Chapter content
        """
        with open(chapter_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def save_chapter_edits(
        project_id: int, chapter_number: int, edits: dict
    ) -> str:
        """
        Save chapter edit data to JSON file.

        Args:
            project_id: Project ID
            chapter_number: Chapter number
            edits: Edit data dictionary

        Returns:
            Path where edits were saved
        """
        dirs = FileManager.create_project_structure(project_id)
        edits_path = Path(dirs["edits"]) / f"chapter_{chapter_number:03d}_edits.json"

        with open(edits_path, "w", encoding="utf-8") as f:
            json.dump(edits, f, indent=2, ensure_ascii=False)

        return str(edits_path)

    @staticmethod
    def load_chapter_edits(project_id: int, chapter_number: int) -> Optional[dict]:
        """
        Load chapter edit data from JSON file.

        Args:
            project_id: Project ID
            chapter_number: Chapter number

        Returns:
            Edit data dictionary or None if not found
        """
        dirs = FileManager.create_project_structure(project_id)
        edits_path = Path(dirs["edits"]) / f"chapter_{chapter_number:03d}_edits.json"

        if not edits_path.exists():
            return None

        with open(edits_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def delete_project(project_id: int) -> bool:
        """
        Delete all files for a project.

        Args:
            project_id: Project ID

        Returns:
            True if successful
        """
        project_dir = FileManager.get_project_dir(project_id)

        if project_dir.exists():
            shutil.rmtree(project_dir)
            return True

        return False

    @staticmethod
    def get_output_epub_path(project_id: int, filename: str = "edited_book.epub") -> str:
        """
        Get the path for output ePub file.

        Args:
            project_id: Project ID
            filename: Output filename

        Returns:
            Path for output ePub
        """
        dirs = FileManager.create_project_structure(project_id)
        return str(Path(dirs["output"]) / filename)
