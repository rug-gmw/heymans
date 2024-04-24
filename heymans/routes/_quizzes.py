import json
from multiprocessing import Process
from flask import Blueprint, request, jsonify
from redis import Redis
from . import no_content, not_found, forbidden, success
from .. import quizzes
from ..database import operations as ops
from ..database.models import NoResultFound
import logging

logger = logging.getLogger('heymans')
quizzes_api_blueprint = Blueprint('api/quizzes', __name__)
redis_client = Redis(decode_responses=True)
redis_client.set('grading_counter', -1)


@quizzes_api_blueprint.route('/new', methods=['POST'])
def new():
    quiz_id = ops.new_quiz(request.json)
    logger.info(f'created quiz: {quiz_id}')
    return jsonify({'quizId': quiz_id})


@quizzes_api_blueprint.route('/list')
def list_():
    return jsonify(ops.list_quizzes())
    
    
@quizzes_api_blueprint.route('/get/<int:quiz_id>')
def get(quiz_id):
    # make sure any pending grades are committed
    quizzes.quiz_grading_task_running(quiz_id)
    try:
        return jsonify(ops.get_quiz(quiz_id))
    except NoResultFound:
        return not_found('Quiz not found')
    
    
@quizzes_api_blueprint.route('/grading/start', methods=['POST'])
def grading_start():
    quiz_id = request.json['quiz_id']
    logger.info(f'start grading quiz: {quiz_id}')
    try:
        quiz = ops.get_quiz(quiz_id)
    except NoResultFound:
        return not_found('Quiz not found')    
    prompt = request.json['prompt']
    model = request.json['model']
    # quizzes.quiz_grading_task(quiz, prompt, model)
    Process(target=quizzes.quiz_grading_task,
            args=(quiz, prompt, model)).start()
    return no_content()


@quizzes_api_blueprint.route('/grading/poll/<int:quiz_id>', methods=['GET'])
def grading_poll(quiz_id):
    if quizzes.quiz_grading_task_running(quiz_id):
        return success(quizzes.GRADING_IN_PROGRESS)
    try:
        quiz = ops.get_quiz(quiz_id)
    except NoResultFound:
        return not_found('Quiz not found')
    # Create a list of bools indicating whether attempts are scored or not
    scored = []
    for question in quiz.get('questions', []):
        for attempt in question.get('attempts', []):
            scored.append(attempt.get('score', None) is not None)
    if all(scored):
        return success(quizzes.GRADING_DONE)
    if any(scored):
        return success(quizzes.GRADING_ABORTED)
    return success(quizzes.NEEDS_GRADING)


@quizzes_api_blueprint.route('/grading/delete', methods=['DELETE'])
def grading_delete():
    redis_client.set('grading_counter', -1)
    return no_content()
    

@quizzes_api_blueprint.route(
    '/grading/push_to_learning_environment/<int:quiz_id>', methods=['GET'])
def grading_push_to_learning_environment(quiz_id):
    return forbidden('Quiz does not exist in learning environment')
