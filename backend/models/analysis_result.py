class AnalysisResult:
    def __init__(self, id, project_id, analysis_type, result_data, created_at):
        self.id = id
        self.project_id = project_id
        self.analysis_type = analysis_type
        self.result_data = result_data
        self.created_at = created_at

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'analysis_type': self.analysis_type,
            'result_data': self.result_data,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
