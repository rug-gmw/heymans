from multiprocessing import Process
from flask import Blueprint, request, jsonify, send_file
from flask_login import login_required, current_user
import tempfile
import zipfile
import os
from io import BytesIO
from redis import Redis
import logging
from . import not_found, forbidden, success, invalid_json, error, no_content
from .. import quizzes, convert, config, report
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
        "name": <str>
    }
    
    Reply JSON example
    ------------------
    {
        "quiz_id": <int>
    }

    Returns
    -------
    200 OK
    """
    name = request.json.get('name')
    user_id = current_user.get_id()
    quiz_id = ops.new_quiz(name, user_id)
    logger.info(f'created quiz: {quiz_id}')
    return jsonify({'quiz_id': quiz_id})


@quizzes_api_blueprint.route('/add/questions/<int:quiz_id>', methods=['POST'])
@login_required
def add_questions(quiz_id):
    """Append questions to an existing quiz. The questions should be a str in 
    Markdown format, according to the example.

    Request JSON example
    --------------------
    {
        "questions": <str>
    }

    Returns
    -------
    200 OK
    400 Bad Request
    403 Forbidden
    404 Not Found
    500 Internal Server Error
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
    """Merge attempt data into an existing quiz. Right now the only format that
    is supported is "brightspace".

    Request JSON example
    --------------------
    {
        "format": <str>,  # optional, defaults to "brightspace"
        "attempts": <str>
    }

    Returns
    -------
    200 OK
    400 Bad Request
    403 Forbidden
    404 Not Found
    500 Internal Server Error
    """
    if not request.is_json:
        return invalid_json()
    attempts = request.json.get('attempts')
    format = request.json.get('format', 'brightspace')
    if format != 'brightspace':
        return error(f'unknown format: {format}')
    user_id = current_user.get_id()
    try:
        quiz_info = ops.get_quiz(quiz_id, user_id)
    except NoResultFound:
        return not_found('Quiz not found')
    # make sure any pending grades are committed
    quizzes.poll_quiz_grading_task(quiz_id, user_id)
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
    
    Reply JSON example
    ------------------    
    [
        {
            "name": <str>,
            "quiz_id": <int>
        },
        ...
    ]

    Returns
    -------
    200 OK
    """
    return jsonify(ops.list_quizzes(current_user.get_id()))
    
    
@quizzes_api_blueprint.route('/get/<int:quiz_id>')
@login_required
def get(quiz_id):
    """Retrieve full quiz details and results.

    Reply JSON example
    ------------------
    {
        "quiz_id": int,
        "name": str,
        "validation": str,  # or None
        "qualitative_error_analysis": str,  # or None
        "questions": [
            {
                "name": str,      # optional
                "text": str,
                "answer_key": [str, str, ...],  # list of strings
                "attempts": [
                    {
                        "attempt_id": int,    # optional
                        "username": str,
                        "answer": str,
                        "score": float,      # or None
                        "feedback": [
                            {
                                "pass": bool,
                                "motivation": str
                            }
                        ]                   # or None
                    },
                    ...
                ]
            },
            ...
        ]
    }

    Returns
    -------
    200 OK
    404 Not Found
    """
    user_id = current_user.get_id()
    # make sure any pending grades are committed
    quizzes.poll_quiz_grading_task(quiz_id, user_id)
    try:
        return jsonify(ops.get_quiz(quiz_id, user_id))
    except NoResultFound:
        return not_found('Quiz not found')
        
        
@quizzes_api_blueprint.route('/export/brightspace/<int:quiz_id>')
@login_required
def export_brightspace(quiz_id):
    """Export the quiz to Brightspace’s question format.
    
    Reply JSON example
    ------------------    
    {
        "content": <str>
    }

    Returns
    -------
    200 OK
    404 Not Found
    """
    user_id = current_user.get_id()
    try:
        quiz_info = ops.get_quiz(quiz_id, user_id)
    except NoResultFound:
        return not_found('Quiz not found')
    content = convert.to_brightspace_exam(quiz_info)
    return jsonify({"content": content})
    

@quizzes_api_blueprint.route('/export/grades/<int:quiz_id>', methods=['POST'])
@login_required
def export_grades(quiz_id):
    """Export the quiz grades in CSV format.
    
    Request JSON example
    --------------------
    {
        "normalize_scores": true,  # optional
        "grading_formula": "groningen" #optional
    }    
    
    Reply JSON example
    ------------------    
    {
        "content": <str>
    }

    Returns
    -------
    200 OK
    404 Not Found
    """
    user_id = current_user.get_id()
    if request.is_json:
        normalize_scores = request.json.get('normalize_scores', True)
        grading_formula = request.json.get('grading_formula', 'groningen')
    else:
        normalize_scores = True
        grading_formula = 'groningen'
    try:
        quiz_info = ops.get_quiz(quiz_id, user_id)        
    except NoResultFound:
        return not_found('Quiz not found')
    
    # Write grades to temporary file
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmp:
        tmp_path = tmp.name

    # Generate the report
    report.calculate_grades(quiz_info, dst=tmp_path,
                            normalize_scores=normalize_scores,
                            grading_formula=grading_formula)        
    # Read the content
    with open(tmp_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Clean up the temporary file
    os.unlink(tmp_path)    
    return jsonify({"content": content})
    
    
@quizzes_api_blueprint.route('/export/feedback/<int:quiz_id>', methods=['POST'])
@login_required
def export_feedback(quiz_id):
    """Export individual feedback as a .zip archive containing .md and .pdf
    files.
    
    Request JSON example
    --------------------
    {
        "normalize_scores": true,  # optional
        "grading_formula": "groningen" #optional
    }      

    Reply
    -----
    Returns a zip file containing all feedback files
    
    Returns
    -------
    200 OK with zip file
    404 Not Found
    """
    user_id = current_user.get_id()
    if request.is_json:
        normalize_scores = request.json.get('normalize_scores', True)
        grading_formula = request.json.get('grading_formula', 'groningen')
    else:
        normalize_scores = True
        grading_formula = 'groningen'    
    try:
        quiz_info = ops.get_quiz(quiz_id, user_id)
    except NoResultFound:
        return not_found('Quiz not found')
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Generate feedback files in temporary directory
        report.generate_feedback(quiz_info, output_folder=temp_dir,
                                 normalize_scores=normalize_scores,
                                 grading_formula=grading_formula)
        
        # Create in-memory zip file
        memory_file = BytesIO()
        
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Walk through temp directory and add all files to zip
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Calculate relative path for better zip structure
                    arcname = os.path.relpath(file_path, temp_dir)
                    zf.write(file_path, arcname)
        
        # Seek to beginning of file so it can be read
        memory_file.seek(0)
        
        # Create filename for the zip
        zip_filename = f'quiz_{quiz_id}_feedback.zip'
        
        # Return the zip file
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )
    
    
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
        
    Reply JSON example
    ------------------            
    {
        "state": <str>
    }

    Returns
    -------
    200 OK
    404 Not Found
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
    400 Bad Request
    404 Not Found
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
    grading_in_progress
        Grading is currently running.
    grading_done
        All attempts are graded.
    grading_error
        Errors occurred and some attempts are not graded.
        
    Reply JSON example
    ------------------            
    {
        "state": <str>
    }        

    Returns
    -------
    200 OK
    404 Not Found
    """
    user_id = current_user.get_id()
    try:
        ops.get_quiz(quiz_id, user_id)
    except NoResultFound:
        return not_found('Quiz not found')
    return jsonify(
        {'state': quizzes.poll_quiz_grading_task(quiz_id, user_id)})


@quizzes_api_blueprint.route('/grading/delete/<int:quiz_id>',
                             methods=['DELETE'])
@login_required
def grading_delete(quiz_id):
    """Delete a quiz and its associated grading artefacts.

    Returns
    -------
    204 No Content
    404 Not Found
    """
    ops.delete_quiz(quiz_id, current_user.get_id())
    return no_content()    

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
    400 Bad Request
    404 Not Found
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
    validation_in_progress
        Validation is currently running.
    validation_done
        Validation finished.
        
    Reply JSON example
    ------------------            
    {
        "state": <str>
    }                

    Returns
    -------
    200 OK
    404 Not Found
    """
    user_id = current_user.get_id()
    if quizzes.quiz_validation_task_running(quiz_id, user_id):
        return jsonify({'state': quizzes.VALIDATION_IN_PROGRESS})
    try:
        quiz = ops.get_quiz(quiz_id, user_id)
    except NoResultFound:
        return not_found('Quiz not found')
    validation = quiz.get('validation')
    if validation is None:
        return jsonify({'state': quizzes.NEEDS_VALIDATION})
    return jsonify({'state': quizzes.VALIDATION_DONE})
