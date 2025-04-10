from multiprocessing import Process
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from redis import Redis
import logging
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from . import no_content, not_found, forbidden, success, invalid_json
from .. import quizzes
from .. import json_schemas
from ..database.operations import quizzes as ops
from ..database.models import NoResultFound

logger = logging.getLogger('heymans')
quizzes_api_blueprint = Blueprint('api/quizzes', __name__)
redis_client = Redis(decode_responses=True)
redis_client.set('grading_counter', -1)


@quizzes_api_blueprint.route('/new', methods=['POST'])
@login_required
def new():
    """Creates a new quiz. See json_schemas.QUIZ."""
    try:
        validate(instance=request.json, schema=json_schemas.QUIZ)
    except ValidationError:
        return invalid_json()
    quiz_id = ops.new_quiz(request.json, current_user.get_id())
    logger.info(f'created quiz: {quiz_id}')
    return jsonify({'quiz_id': quiz_id})


@quizzes_api_blueprint.route('/list')
@login_required
def list_():
    """Gets a list of all quizzes."""
    return jsonify(ops.list_quizzes(current_user.get_id()))
    
    
@quizzes_api_blueprint.route('/get/<int:quiz_id>')
@login_required
def get(quiz_id):
    """Gets a single quiz."""
    user_id = current_user.get_id()
    # make sure any pending grades are committed
    quizzes.quiz_grading_task_running(quiz_id, user_id)
    try:
        return jsonify(ops.get_quiz(quiz_id, user_id))
    except NoResultFound as e:
        return not_found('Quiz not found')
    
    
@quizzes_api_blueprint.route('/grading/start', methods=['POST'])
@login_required
def grading_start():
    """Start grading a single quiz. See json_schemas.GRADING_START. Grading
    occurs in the background and needs to be polled through /api/grading/poll.
    """
    try:
        validate(instance=request.json, schema=json_schemas.GRADING_START)
    except ValidationError as e:
        return invalid_json()    
    quiz_id = request.json['quiz_id']
    logger.info(f'start grading quiz: {quiz_id}')
    try:
        quiz = ops.get_quiz(quiz_id, current_user.get_id())
    except NoResultFound:
        return not_found('Quiz not found')    
    model = request.json['model']
    Process(target=quizzes.quiz_grading_task,
            args=(quiz, model)).start()
    return no_content()


@quizzes_api_blueprint.route('/grading/poll/<int:quiz_id>', methods=['GET'])
@login_required
def grading_poll(quiz_id):
    """Checks whether grading of a quiz is in progress, done, needed, or 
    aborted.
    """
    user_id = current_user.get_id()
    if quizzes.quiz_grading_task_running(quiz_id, user_id):
        return success(quizzes.GRADING_IN_PROGRESS)
    try:
        quiz = ops.get_quiz(quiz_id, user_id)
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


@quizzes_api_blueprint.route('/grading/delete/<int:quiz_id>',
                             methods=['DELETE'])
@login_required
def grading_delete(quiz_id):
    """Deletes a quiz"""
    ops.delete_quiz(quiz_id, current_user.get_id())
    

@quizzes_api_blueprint.route(
    '/grading/push_to_learning_environment/<int:quiz_id>', methods=['GET'])
def grading_push_to_learning_environment(quiz_id):
    """Pushes the grades for a quiz to the learning environment. Currently
    not implemented.
    """
    return forbidden('Quiz does not exist in learning environment')
