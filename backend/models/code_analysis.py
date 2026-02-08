import json


class CodeAnalysis:
    def __init__(self, id, project_id, file_hash, analysis_type, narrative_json,
                 model_used, tokens_used, generation_time_ms, created_at, expires_at):
        self.id = id
        self.project_id = project_id
        self.file_hash = file_hash
        self.analysis_type = analysis_type
        self.narrative_json = narrative_json
        self.model_used = model_used
        self.tokens_used = tokens_used
        self.generation_time_ms = generation_time_ms
        self.created_at = created_at
        self.expires_at = expires_at

    def get_narrative(self):
        """Parse and return the narrative JSON as a dictionary"""
        if isinstance(self.narrative_json, str):
            return json.loads(self.narrative_json)
        return self.narrative_json

    def to_dict(self):
        """Convert to dictionary for JSON response"""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'file_hash': self.file_hash,
            'analysis_type': self.analysis_type,
            'narrative': self.get_narrative(),
            'model_used': self.model_used,
            'tokens_used': self.tokens_used,
            'generation_time_ms': self.generation_time_ms,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
