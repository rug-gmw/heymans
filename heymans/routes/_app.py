import json
from http import HTTPStatus
from flask import Blueprint, request, jsonify, make_response, render_template
from redis import Redis
import logging

logger = logging.getLogger('heymans')
app_blueprint = Blueprint('app', __name__)


@app_blueprint.route('/quiz', methods=['GET'])
def quiz():
    return render_template('quiz.html')
