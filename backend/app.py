from flask import Flask
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
jwt = JWTManager(app)
CORS(app)

# Register routes
from routes import init_routes
init_routes(app)

if __name__ == '__main__':
    from init_db import init_database
    init_database()
    app.run(debug=True, host='0.0.0.0', port=5000)
