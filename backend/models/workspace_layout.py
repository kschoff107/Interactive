class WorkspaceLayout:
    def __init__(self, id, project_id, analysis_type, layout_data, created_at, updated_at):
        self.id = id
        self.project_id = project_id
        self.analysis_type = analysis_type
        self.layout_data = layout_data
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'analysis_type': self.analysis_type,
            'layout_data': self.layout_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
