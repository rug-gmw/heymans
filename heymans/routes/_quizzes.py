from multiprocessing import Process
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from redis import Redis
import logging
from . import no_content, not_found, forbidden, success, invalid_json, error
from .. import quizzes, convert
from ..database.operations import quizzes as ops
from ..database.models import NoResultFound

logger = logging.getLogger('heymans')
quizzes_api_blueprint = Blueprint('api/quizzes', __name__)
redis_client = Redis(decode_responses=True)
redis_client.set('grading_counter', -1)


@quizzes_api_blueprint.route('/new', methods=['POST'])
@login_required
def new():
    """Creates an empty quiz and returns its id.

    JSON post data (example):
        {"name": "quiz name"}
    
    Returns:
        Status: OK (200)
        JSON (example): {"quiz_id": 1}
    """
    name = request.json.get('name')
    user_id = current_user.get_id()
    quiz_id = ops.new_quiz(name, user_id)
    logger.info(f'created quiz: {quiz_id}')
    return jsonify({'quiz_id': quiz_id})


@quizzes_api_blueprint.route('/add/questions/<int:quiz_id>', methods=['POST'])
@login_required
def add_questions(quiz_id):
    """Adds questions to an existing quiz.
    
    JSON post data (example):
        {"questions": "markdown questions and answer keys"}
    
    Returns:
        Status: OK (200)
        JSON (example): {"message": "success"}
    """
    if not request.is_json:
        return invalid_json()
    user_id = current_user.get_id()
    questions = request.json.get('questions')
    try:
        quiz_info = convert.from_markdown_exam(questions, quiz_id)
    except ValueError as e:
        error_msg = f'failed to convert questions to json: {e}'
        return error(error_msg)
    try:
        ops.update_quiz(quiz_id, quiz_info, user_id)
    except NoResultFound:
        return not_found()
    except PermissionError:
        return forbidden()
    logger.info(f'added questions to quiz {quiz_id}')
    return success()


@quizzes_api_blueprint.route('/add/attempts/<int:quiz_id>', methods=['POST'])
@login_required
def add_attempts(quiz_id):
    """Adds student attempts to an existing quiz.
    
    JSON post data (example):
        {"attempts": "brightspace result data"}
    
    Returns:
        Status: OK (200)
        JSON (example): {"message": "success"}
    """
    if not request.is_json:
        return invalid_json()
    attempts = request.json.get('attempts')
    user_id = current_user.get_id()
    try:
        quiz_info = ops.get_quiz(quiz_id, user_id)
    except NoResultFound:
        return not_found('Quiz not found')
    # make sure any pending grades are committed
    quizzes.quiz_grading_task_running(quiz_id, user_id)
    try:
        quiz_info = convert.merge_brightspace_attempts(quiz_info, attempts)
    except Exception as e:
        error_message = f'failed to merge attempts: {e}'
        return error(error_message)
    try:
        ops.update_quiz(quiz_id, quiz_info, user_id)
    except NoResultFound:
        return not_found()
    except PermissionError:
        return forbidden()
    logger.info(f'added attempts to quiz {quiz_id}')
    return success()


@quizzes_api_blueprint.route('/list')
@login_required
def list_():
    """Gets a list of all quizzes.
    
    Returns:
        Status: OK (200)
        JSON (example): [{"name": "quiz name", "quiz_id": 1}]
    """
    return jsonify(ops.list_quizzes(current_user.get_id()))
    
    
@quizzes_api_blueprint.route('/get/<int:quiz_id>')
@login_required
def get(quiz_id):
    """Gets the results for a single quiz.
    
    Returns:
        Status: OK (200)
        JSON: see heymans.json_schemas.QUIZ
    """
    user_id = current_user.get_id()
    # make sure any pending grades are committed
    quizzes.quiz_grading_task_running(quiz_id, user_id)
    try:
        return jsonify(ops.get_quiz(quiz_id, user_id))
    except NoResultFound:
        return not_found('Quiz not found')
        
        
@quizzes_api_blueprint.route('/export/brightspace/<int:quiz_id>')
@login_required
def export_brightspace(quiz_id):
    """DUMMY IMPLEMENTATION
    
    Returns an export of the quiz questions in Brightspace format.
    
    Returns:
        Status: OK (200)
        JSON (example): {"text": "brightspace export"}
    """    
    
@quizzes_api_blueprint.route('/state/<int:quiz_id>')
@login_required
def state(quiz_id):
    """DUMMY IMPLEMENTATION
    
    Gets the state for a single quiz.
    
    0 - If there is no data
    1 - If there are questions, but no attempts
    2 - If there are ungraded attempts
    3 - If there are graded attempts    
    
    Returns:
        Status: OK (200)
        JSON (example): {"state": 0}
    """
    user_id = current_user.get_id()
    try:
        return jsonify({"state" : quizzes.state(quiz_id, user_id)})
    except NoResultFound:
        return not_found('Quiz not found')
    
    
@quizzes_api_blueprint.route('/grading/start/<int:quiz_id>', methods=['POST'])
@login_required
def grading_start(quiz_id):
    """Start grading a single quiz.
    
    Grading occurs in the background and needs to be polled through
    /api/grading/poll/<quiz_id>.
    
    JSON post data (example):
        {"model": "gpt-4.1"}
    
    Returns:
        Status: OK (200)
        JSON (example): {"message": "success"}
    """
    model = request.json.get('model')

    # Validate presence of required parameters
    if not quiz_id or not model:
        return invalid_json()  # 400 Bad Request

    logger.info(f'start grading quiz: {quiz_id}')
    try:
        quiz = ops.get_quiz(quiz_id, current_user.get_id())
    except NoResultFound:
        return not_found('Quiz not found')

    Process(target=quizzes.quiz_grading_task, args=(quiz, model)).start()
    return success()


@quizzes_api_blueprint.route('/grading/poll/<int:quiz_id>', methods=['GET'])
@login_required
def grading_poll(quiz_id):
    """Checks whether grading of a quiz is in progress, done, needed, or 
    aborted.
    
    Returns:
        Status: OK (200)
        JSON (example): {"message": "needs_grading"}
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
    

# ---------------------------------------------------------------------------
# Validation API end‑points
# ---------------------------------------------------------------------------

@quizzes_api_blueprint.route('/validation/start/<int:quiz_id>', methods=['POST'])
@login_required
def validation_start(quiz_id):
    """Start validation of the quiz questions that have already been uploaded.
    
    The task runs in a background process (see quizzes.quiz_validation_task).
    Results can be polled via /validation/poll.
    
    JSON post data (example):
        {"model": "gpt-4.1"}
    
    Returns:
        Status: OK (200)
        JSON (example): {"message": "success"}
    """
    model = request.json.get('model')

    # Validate presence of required parameter
    if not model:
        return invalid_json()  # 400 Bad Request

    user_id = current_user.get_id()
    logger.info(f'start validation for quiz: {quiz_id} using model: {model}')

    try:
        quiz = ops.get_quiz(quiz_id, user_id)
    except NoResultFound:
        return not_found('Quiz not found')

    # Fire‑and‑forget background process
    Process(target=quizzes.quiz_validation_task, args=(quiz, model)).start()
    return no_content()


@quizzes_api_blueprint.route('/validation/poll/<int:quiz_id>', methods=['GET'])
@login_required
def validation_poll(quiz_id):
    """Poll the state of the validation task.
    
    Returns:
        Status: OK (200)
        JSON (example): {"message": "needs_validation"}
    """
    user_id = current_user.get_id()
    if quizzes.quiz_validation_task_running(quiz_id, user_id):
        return success(quizzes.VALIDATION_IN_PROGRESS)
    try:
        quiz = ops.get_quiz(quiz_id, user_id)
    except NoResultFound:
        return not_found('Quiz not found')
    validation = quiz.get('validation')
    if validation is None:
        return success(quizzes.NEEDS_VALIDATION)
    return success(quizzes.VALIDATION_DONE)
