class Workspace:
    def __init__(self, id, project_id, analysis_type, name, sort_order=0,
                 created_at=None, updated_at=None):
        self.id = id
        self.project_id = project_id
        self.analysis_type = analysis_type
        self.name = name
        self.sort_order = sort_order
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'analysis_type': self.analysis_type,
            'name': self.name,
            'sort_order': self.sort_order,
            'created_at': self.created_at.isoformat() if hasattr(self.created_at, 'isoformat') else self.created_at,
            'updated_at': self.updated_at.isoformat() if hasattr(self.updated_at, 'isoformat') else self.updated_at,
        }
