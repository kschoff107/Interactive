"""Project model for code analysis projects."""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Project(Base):
    """Project model representing a code analysis project."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    repository_url = Column(String(500))
    repository_path = Column(String(500))
    language = Column(String(50))
    framework = Column(String(50))
    is_active = Column(Boolean, default=True, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_analyzed_at = Column(DateTime(timezone=True))

    # Relationships
    owner = relationship("User", back_populates="projects")
    analysis_results = relationship("AnalysisResult", back_populates="project", cascade="all, delete-orphan")
    workspace_notes = relationship("WorkspaceNote", back_populates="project", cascade="all, delete-orphan")
    workspace_layouts = relationship("WorkspaceLayout", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}', owner_id={self.owner_id})>"
