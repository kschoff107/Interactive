from flask import Blueprint

def init_routes(app):
    """Initialize all routes"""
    from .auth import auth_bp
    from .projects import projects_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(projects_bp, url_prefix='/api/projects')
