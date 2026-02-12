# Backward-compatibility shim — parser moved to parsers/routes/flask_parser.py
from .routes.flask_parser import RouteVisitor, FlaskRoutesParser  # noqa: F401
