import json
from http import HTTPStatus
from flask import Blueprint, request, jsonify, make_response
from redis import Redis
import logging

logger = logging.getLogger('heymans')
quizzes_api_blueprint = Blueprint('api/quizzes', __name__)
redis_client = Redis()
redis_client.set('grading_counter', -1)


@quizzes_api_blueprint.route('/new', methods=['POST'])
def new():
    logger.info('creating new quiz')
    redis_client.set('quizz', json.dumps(request.json))
    return jsonify({'quizId': 1})


@quizzes_api_blueprint.route('/list')
def list_():
    return jsonify([1])
    
    
@quizzes_api_blueprint.route('/get/<int:quiz_id>')
def get(quiz_id):
    return jsonify(json.loads(redis_client.get('quizz')))
    
    
@quizzes_api_blueprint.route('/grading/start', methods=['POST'])
def grading_start():
    redis_client.set('grading_counter', 0)
    return make_response('', HTTPStatus.NO_CONTENT)


@quizzes_api_blueprint.route('/grading/poll', methods=['GET'])
def grading_poll():
    grading_counter = int(redis_client.get('grading_counter'))
    if grading_counter < 0:
        return jsonify('needs_grading')
    quiz_data = json.loads(redis_client.get('quizz'))
    if grading_counter >= len(quiz_data[0]['attempts']):
        return jsonify('grading_done')
    quiz_data[0]['attempts'][grading_counter]['score'] = 1
    quiz_data[0]['attempts'][grading_counter]['feedback'] = 'test feedback'
    redis_client.set('grading_counter', grading_counter + 1)
    redis_client.set('quizz', json.dumps(quiz_data))
    return jsonify('grading_in_progress')


@quizzes_api_blueprint.route('/grading/delete', methods=['DELETE'])
def grading_delete():
    redis_client.set('grading_counter', -1)
    return make_response('', HTTPStatus.NO_CONTENT)
    

@quizzes_api_blueprint.route(
    '/grading/push_to_learning_environment/<int:quiz_id>', methods=['GET'])
def grading_push_to_learning_environment(quiz_id):
    return jsonify({'error': 'Quiz does not exist in learning environment'}), \
        HTTPStatus.FORBIDDEN
