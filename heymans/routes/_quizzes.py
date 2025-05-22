from multiprocessing import Process
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from redis import Redis
import logging
from . import not_found, forbidden, success, invalid_json, error
from .. import quizzes, convert, config
from ..database.operations import quizzes as ops
from ..database.models import NoResultFound

logger = logging.getLogger('heymans')
quizzes_api_blueprint = Blueprint('api/quizzes', __name__)
redis_client = Redis(decode_responses=True)
redis_client.set('grading_counter', -1)


@quizzes_api_blueprint.route('/new', methods=['POST'])
@login_required
def new():
    """Create a new (empty) quiz and return its identifier.

    Request JSON example
    --------------------
    {
        "name": "Quiz name"
    }

    Returns
    -------
    200 OK
        JSON: {"quiz_id": <int>}
    """
    name = request.json.get('name')
    user_id = current_user.get_id()
    quiz_id = ops.new_quiz(name, user_id)
    logger.info(f'created quiz: {quiz_id}')
    return jsonify({'quiz_id': quiz_id})


@quizzes_api_blueprint.route('/add/questions/<int:quiz_id>', methods=['POST'])
@login_required
def add_questions(quiz_id):
    """Append questions (in Markdown) to an existing quiz.

    Request JSON example
    --------------------
    {
        "questions": "<markdown questions and answer keys>"
    }

    Returns
    -------
    200 OK
        JSON: {"message": "success"}
    400 Bad Request
        Malformed or non‑JSON body.
    403 Forbidden
        User does not own the quiz.
    404 Not Found
        Quiz with *quiz_id* does not exist.
    500 Internal Server Error
        Markdown conversion failed.
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
    """Merge Brightspace attempt data into an existing quiz.

    Request JSON example
    --------------------
    {
        "attempts": "<Brightspace result data>"
    }

    Returns
    -------
    200 OK
        JSON: {"message": "success"}
    400 Bad Request
        Malformed or non‑JSON body.
    403 Forbidden
        User does not own the quiz.
    404 Not Found
        Quiz with *quiz_id* does not exist.
    500 Internal Server Error
        Merge failed.
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
    """Return a list of quizzes owned by the current user.

    Returns
    -------
    200 OK
        JSON: [{"name": <str>, "quiz_id": <int>}, ...]
    """
    return jsonify(ops.list_quizzes(current_user.get_id()))
    
    
@quizzes_api_blueprint.route('/get/<int:quiz_id>')
@login_required
def get(quiz_id):
    """Retrieve full quiz details and results.

    JSON schema
    -----------
    See ``heymans.json_schemas.QUIZ``.

    Returns
    -------
    200 OK
        Full quiz object.
    404 Not Found
        Quiz not found.
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
    """Export the quiz to Brightspace’s question format.

    Returns
    -------
    200 OK
        JSON: {"content": "<Brightspace export string>"}
    404 Not Found
        Quiz not found.
    """
    user_id = current_user.get_id()
    try:
        quiz_info = ops.get_quiz(quiz_id, user_id)
    except NoResultFound:
        return not_found('Quiz not found')
    content = convert.to_brightspace_exam(quiz_info)
    return jsonify({"content": content})
    
    
@quizzes_api_blueprint.route('/state/<int:quiz_id>')
@login_required
def state(quiz_id):
    """Report the current lifecycle state of a quiz.

    Possible states
    ---------------
    empty
        Quiz has no questions.
    has_questions
        Quiz has questions but no attempts.
    has_attempts
        At least one attempt exists, but some attempts lack a score.
    has_scores
        All attempts have scores.

    Returns
    -------
    200 OK
        JSON: {"state": "<state string>"}
    404 Not Found
        Quiz not found.
    """
    user_id = current_user.get_id()
    try:
        quiz_info = ops.get_quiz(quiz_id, user_id)
    except NoResultFound:
        return not_found('Quiz not found')    
    try:
        return jsonify({"state" : quizzes.state(quiz_info)})
    except NoResultFound:
        return not_found('Quiz not found')
    
    
@quizzes_api_blueprint.route('/grading/start/<int:quiz_id>', methods=['POST'])
@login_required
def grading_start(quiz_id):
    """Kick off background grading for a single quiz.

    The grading task is asynchronous; poll its status via
    ``/api/grading/poll/<quiz_id>``.

    Request JSON example
    --------------------
    {
        "model": "gpt-4.1"  # optional
    }

    Returns
    -------
    200 OK
        JSON: {"message": "success"}
    400 Bad Request
        Missing *model* parameter.
    404 Not Found
        Quiz not found.
    """
    model = request.json.get('model', config.default_model)

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
    """Poll the grading task and return its current status.

    Status codes
    ------------
    needs_grading
        No grading has been started.
    in_progress
        Grading is currently running.
    done
        All attempts are graded.
    aborted
        Grading was interrupted; some attempts are graded.

    Returns
    -------
    200 OK
        JSON: {"message": "<status string>"}
    404 Not Found
        Quiz not found.
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
    """Delete a quiz and its associated grading artefacts.

    Returns
    -------
    204 No Content
        Quiz successfully deleted.
    404 Not Found
        Quiz not found.
    """
    ops.delete_quiz(quiz_id, current_user.get_id())
    

# ---------------------------------------------------------------------------
# Validation API end‑points
# ---------------------------------------------------------------------------

@quizzes_api_blueprint.route('/validation/start/<int:quiz_id>', methods=['POST'])
@login_required
def validation_start(quiz_id):
    """Start background validation of uploaded quiz questions.

    The task runs in a detached process; its status is polled through
    ``/validation/poll``.

    Request JSON example
    --------------------
    {
        "model": "gpt-4.1"  # optional
    }

    Returns
    -------
    200 OK
        JSON: {"message": "success"}
    400 Bad Request
        Missing *model* parameter.
    404 Not Found
        Quiz not found.
    """
    model = request.json.get('model', config.default_model)

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
    return success()


@quizzes_api_blueprint.route('/validation/poll/<int:quiz_id>', methods=['GET'])
@login_required
def validation_poll(quiz_id):
    """Poll the validation task for a quiz and return its status.

    Status codes
    ------------
    needs_validation
        No validation has been started.
    in_progress
        Validation is currently running.
    done
        Validation finished.

    Returns
    -------
    200 OK
        JSON: {"message": "<status string>"}
    404 Not Found
        Quiz not found.
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