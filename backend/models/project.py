class Project:
    def __init__(self, id, user_id, name, description, source_type, git_url,
                 file_path, language, framework, created_at, updated_at,
                 has_database_schema=False, has_runtime_flow=False, last_upload_date=None):
        self.id = id
        self.user_id = user_id
        self.name = name
        self.description = description
        self.source_type = source_type
        self.git_url = git_url
        self.file_path = file_path
        self.language = language
        self.framework = framework
        self.has_database_schema = has_database_schema
        self.has_runtime_flow = has_runtime_flow
        self.last_upload_date = last_upload_date
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self):
        """Convert to dictionary"""
        # Convert datetime objects to ISO format strings for JSON serialization
        created_at = self.created_at.isoformat() if hasattr(self.created_at, 'isoformat') else self.created_at
        updated_at = self.updated_at.isoformat() if hasattr(self.updated_at, 'isoformat') else self.updated_at
        last_upload_date = self.last_upload_date.isoformat() if hasattr(self.last_upload_date, 'isoformat') else self.last_upload_date

        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'description': self.description,
            'source_type': self.source_type,
            'git_url': self.git_url,
            'file_path': self.file_path,
            'language': self.language,
            'framework': self.framework,
            'has_database_schema': self.has_database_schema,
            'has_runtime_flow': self.has_runtime_flow,
            'last_upload_date': last_upload_date,
            'created_at': created_at,
            'updated_at': updated_at
        }
