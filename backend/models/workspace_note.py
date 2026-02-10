class WorkspaceNote:
    def __init__(self, id, project_id, analysis_type, note_text, position_x,
                 position_y, color, created_at, updated_at, workspace_id=None):
        self.id = id
        self.project_id = project_id
        self.analysis_type = analysis_type
        self.note_text = note_text
        self.position_x = position_x
        self.position_y = position_y
        self.color = color
        self.created_at = created_at
        self.updated_at = updated_at
        self.workspace_id = workspace_id

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'analysis_type': self.analysis_type,
            'note_text': self.note_text,
            'position_x': self.position_x,
            'position_y': self.position_y,
            'color': self.color,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'workspace_id': self.workspace_id
        }
