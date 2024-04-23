import json
from http import HTTPStatus
from flask import Blueprint, request, jsonify, make_response
from redis import Redis
from ..database import operations as ops
import logging

logger = logging.getLogger('heymans')
quizzes_api_blueprint = Blueprint('api/quizzes', __name__)
redis_client = Redis()
redis_client.set('grading_counter', -1)


@quizzes_api_blueprint.route('/new', methods=['POST'])
def new():
    logger.info('creating new quiz')
    quiz_id = ops.new_quiz(request.json)
    return jsonify({'quizId': quiz_id})


@quizzes_api_blueprint.route('/list')
def list_():
    return jsonify(ops.list_quizzes())
    
    
@quizzes_api_blueprint.route('/get/<int:quiz_id>')
def get(quiz_id):
    return jsonify(ops.get_quiz(quiz_id))
    
    
@quizzes_api_blueprint.route('/grading/start', methods=['POST'])
def grading_start():
    redis_client.set('grading_counter', 0)
    return make_response('', HTTPStatus.NO_CONTENT)


@quizzes_api_blueprint.route('/grading/poll/<int:quiz_id>', methods=['GET'])
def grading_poll(quiz_id):
    grading_counter = int(redis_client.get('grading_counter'))
    logger.info(f'grading counter: {grading_counter}')
    if grading_counter < 0:
        return jsonify('needs_grading')
    quiz_data = json.loads(redis_client.get('quiz'))
    if grading_counter >= len(quiz_data['questions'][0]['attempts']):
        return jsonify('grading_done')
    quiz_data['questions'][0]['attempts'][grading_counter]['score'] = 1
    quiz_data['questions'][0]['attempts'][grading_counter]['feedback'] = \
        'test feedback'
    redis_client.set('grading_counter', grading_counter + 1)
    redis_client.set('quiz', json.dumps(quiz_data))
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
