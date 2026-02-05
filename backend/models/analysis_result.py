"""Analysis result model for storing code analysis data."""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class AnalysisResult(Base):
    """Analysis result model storing code analysis output."""

    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    analysis_type = Column(String(50), nullable=False, index=True)  # e.g., 'ast', 'dependencies', 'complexity'
    file_path = Column(String(500))
    module_name = Column(String(200), index=True)
    result_data = Column(JSON, nullable=False)  # Store analysis results as JSON
    metadata = Column(JSON)  # Additional metadata about the analysis
    status = Column(String(20), default='completed', nullable=False)  # 'pending', 'completed', 'failed'
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="analysis_results")

    def __repr__(self):
        return f"<AnalysisResult(id={self.id}, project_id={self.project_id}, type='{self.analysis_type}')>"
