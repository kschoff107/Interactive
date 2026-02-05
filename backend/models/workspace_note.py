"""Workspace note model for user annotations."""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class WorkspaceNote(Base):
    """Workspace note model for user annotations and comments."""

    __tablename__ = "workspace_notes"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200))
    content = Column(Text, nullable=False)
    note_type = Column(String(50), default='general')  # 'general', 'code-comment', 'todo', 'insight'
    position = Column(JSON)  # Store x, y coordinates for canvas positioning
    related_entity = Column(JSON)  # Store reference to code element (file, class, function)
    color = Column(String(20), default='yellow')
    is_pinned = Column(Integer, default=0)  # Use Integer for SQLite compatibility (0=False, 1=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="workspace_notes")
    user = relationship("User", back_populates="workspace_notes")

    def __repr__(self):
        return f"<WorkspaceNote(id={self.id}, project_id={self.project_id}, user_id={self.user_id})>"
