"""Workspace layout model for saving canvas state."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class WorkspaceLayout(Base):
    """Workspace layout model for saving canvas state and configurations."""

    __tablename__ = "workspace_layouts"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    layout_data = Column(JSON, nullable=False)  # Store node positions, zoom, pan, etc.
    view_settings = Column(JSON)  # Store view preferences (filters, grouping, colors)
    is_default = Column(Boolean, default=False, nullable=False)
    is_shared = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="workspace_layouts")
    user = relationship("User", back_populates="workspace_layouts")

    def __repr__(self):
        return f"<WorkspaceLayout(id={self.id}, name='{self.name}', project_id={self.project_id})>"
