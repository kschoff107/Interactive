class Project:
    def __init__(self, id, user_id, name, description, source_type, git_url,
                 file_path, language, framework, created_at, updated_at):
        self.id = id
        self.user_id = user_id
        self.name = name
        self.description = description
        self.source_type = source_type
        self.git_url = git_url
        self.file_path = file_path
        self.language = language
        self.framework = framework
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self):
        """Convert to dictionary"""
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
            'created_at': self.created_at,  # SQLite returns timestamps as strings
            'updated_at': self.updated_at   # SQLite returns timestamps as strings
        }
