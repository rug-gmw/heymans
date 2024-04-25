from http import HTTPStatus
from flask import jsonify, make_response
from ._replies import no_content, not_found, success, forbidden, invalid_json
from ._quizzes import quizzes_api_blueprint
from ._app import app_blueprint
