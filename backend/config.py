import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///code_visualizer.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max upload
    STORAGE_PATH = os.environ.get('STORAGE_PATH') or os.path.join(os.path.dirname(os.path.dirname(__file__)), 'storage')

    # Anthropic API Configuration
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
    ANTHROPIC_MODEL = os.environ.get('ANTHROPIC_MODEL', 'claude-3-5-sonnet-20241022')
    ANTHROPIC_MAX_TOKENS = int(os.environ.get('ANTHROPIC_MAX_TOKENS', 4000))
    ANTHROPIC_TEMPERATURE = float(os.environ.get('ANTHROPIC_TEMPERATURE', 0.3))
    ANALYSIS_CACHE_DAYS = int(os.environ.get('ANALYSIS_CACHE_DAYS', 30))
