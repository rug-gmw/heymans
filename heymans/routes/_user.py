import json
from flask import Blueprint, request, jsonify, session
from flask_login import login_user, login_required, UserMixin
import logging
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from . import no_content
from .. import json_schemas
from ..database.operations import documents as ops

logger = logging.getLogger('heymans')
user_api_blueprint = Blueprint('api/user', __name__)


class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id
        logger.info(f'initializing user id: {self.id}')


@user_api_blueprint.route('/login/<int:user_id>', methods=['GET'])
def login(user_id):
    login_user(User(user_id))
    logger.info(f'logged in as {user_id}')
    return no_content()
    
    
@user_api_blueprint.route('/logout', methods=['GET'])
def logout():
    logout_user()
    logger.info('logged out')
    return no_content()
