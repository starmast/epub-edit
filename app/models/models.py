"""SQLAlchemy ORM models."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
from datetime import datetime
from typing import Optional


class Project(Base):
    """Project model representing an ePub editing project."""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    original_file_path = Column(String(500), nullable=False)
    book_metadata = Column(JSON, nullable=True)  # title, author, language, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    processing_status = Column(String(50), default="idle")  # idle, processing, paused, completed
    llm_settings = Column(JSON, nullable=True)  # endpoint, encrypted_api_key, model, max_tokens

    # Relationships
    chapters = relationship("Chapter", back_populates="project", cascade="all, delete-orphan")
    processing_jobs = relationship("ProcessingJob", back_populates="project", cascade="all, delete-orphan")

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "original_file_path": self.original_file_path,
            "metadata": self.book_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "processing_status": self.processing_status,
            "llm_settings": self.llm_settings,
        }


class Chapter(Base):
    """Chapter model representing a chapter in an ePub book."""
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    title = Column(String(500), nullable=True)
    original_content_path = Column(String(500), nullable=False)
    edited_content_path = Column(String(500), nullable=True)
    processing_status = Column(
        String(50),
        default="not_started"
    )  # not_started, queued, in_progress, completed, failed
    error_message = Column(Text, nullable=True)
    token_count = Column(Integer, default=0)
    word_count = Column(Integer, default=0)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="chapters")

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "chapter_number": self.chapter_number,
            "title": self.title,
            "original_content_path": self.original_content_path,
            "edited_content_path": self.edited_content_path,
            "processing_status": self.processing_status,
            "error_message": self.error_message,
            "token_count": self.token_count,
            "word_count": self.word_count,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }


class ProcessingJob(Base):
    """Processing job model for tracking batch processing."""
    __tablename__ = "processing_jobs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    start_chapter = Column(Integer, nullable=False)
    end_chapter = Column(Integer, nullable=False)
    worker_count = Column(Integer, default=3)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), default="running")  # running, paused, completed, failed
    error_message = Column(Text, nullable=True)
    progress_data = Column(JSON, nullable=True)  # Store progress metrics

    # Relationships
    project = relationship("Project", back_populates="processing_jobs")

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "start_chapter": self.start_chapter,
            "end_chapter": self.end_chapter,
            "worker_count": self.worker_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "error_message": self.error_message,
            "progress_data": self.progress_data,
        }
