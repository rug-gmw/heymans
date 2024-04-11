import os
os.environ['USE_FLASK_SQLALCHEMY'] = '1'
from flask import Flask, Config, request
from . import config
from .routes import quizzes_api_blueprint
from .database.models import db
import logging
logger = logging.getLogger('heymans')
logging.basicConfig(level=logging.INFO, force=True)


class HeymansConfig(Config):
    SECRET_KEY = config.flask_secret_key
    SQLALCHEMY_DATABASE_URI = 'sqlite:///heymans.db'


def create_app(config_class=HeymansConfig):
    app = Flask(__name__, static_url_path='/static')
    app.config.from_object(config_class)
    app.register_blueprint(quizzes_api_blueprint, url_prefix='/api/quizzes')
    # Initialize the databasea
    db.init_app(app)
    with app.app_context():
        db.create_all()
    
    @app.after_request
    def log_request(response):
        # Log all incoming requests
        user_agent = request.headers.get('User-Agent')
        if user_agent is not None and 'bot' not in user_agent.lower():
            logger.info(f'request: {request.full_path}')
        return response

    return app
