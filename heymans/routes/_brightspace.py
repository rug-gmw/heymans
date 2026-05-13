from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from requests.exceptions import HTTPError
import logging
from .. import report, config
from ..brightspace import get_brightspace
from . import internal_server_error, forbidden, invalid_json, success
from ..database.operations import quizzes as ops
from ..database.models import NoResultFound

logger = logging.getLogger('heymans')
brightspace_api_blueprint = Blueprint('api/brightspace', __name__)


@brightspace_api_blueprint.route(
    '/list/courses',
    methods=['GET'])
@login_required
def list_courses():
    """Returns a list of courses for the current user.
    
    Reply JSON example
    ------------------
    [
        {
            "name": "Thinking and Deciding",
            "code": "PSMIN22",
            "bs_org_unit_id": 12345
        },
        ...
    ]
    
    Returns
    -------
    200 OK
    500 Internal Server Error
    """    
    try:
        course_list = get_brightspace().list_courses()
    except Exception as e:
        return internal_server_error(str(e))
    return jsonify(course_list)


@brightspace_api_blueprint.route(
    'list/courses/<int:bs_org_unit_id>/quizzes',
    methods=['GET'])
@login_required
def list_course_quizzes(bs_org_unit_id):
    """Returns a list of quizzes within a course for the current user.
    
    Reply JSON example
    ------------------
    [
        {
            "name": "Practice exam",
            "bs_quiz_id": 12344
        },
        ...
    ]
    
    Returns
    -------
    200 OK
    403 Forbidden
    500 Internal Server Error
    """
    try:
        quiz_list = get_brightspace().list_course_quizzes(bs_org_unit_id)
    except Exception as e:
        return _forbidden_or_internal_server_error(e)
    return jsonify(quiz_list)


@brightspace_api_blueprint.route(
    '/import/courses/<int:bs_org_unit_id>/quizzes/<int:bs_quiz_id>',
    methods=['GET'])
@login_required    
def import_course_quiz(bs_org_unit_id, bs_quiz_id):
    """Imports a quiz from Brightspace to Heymans and returns the identifier.
    
    Reply JSON example
    ------------------
    {
        "quiz_id": <int>
    }

    Returns
    -------
    200 OK
    403 Forbidden
    500 Internal Server Error
    """
    try:
        quiz_info = get_brightspace().get_quiz(bs_org_unit_id, bs_quiz_id)
    except Exception as e:
        return _forbidden_or_internal_server_error(e)
    user_id = current_user.get_id()
    quiz_id = ops.new_quiz('dummy', user_id)
    ops.update_quiz(quiz_id, quiz_info, user_id)
    return jsonify({'quiz_id': quiz_id})


@brightspace_api_blueprint.route(
    '/export/courses/<int:bs_org_unit_id>/quizzes',
    methods=['POST'])
@login_required    
def export_course_quiz(bs_org_unit_id):
    """Exports a quiz from Heymans to Brightspace and returns the identifier.
    
    Request JSON example
    --------------------
    {
        "quiz_id": <int>
    }    
    
    Reply JSON example
    ------------------
    {
        "bs_quiz_id": <int>
    }

    Returns
    -------
    200 OK
    400 Bad Request
    403 Forbidden
    500 Internal Server Error    
    """    
    user_id = current_user.get_id()
    quiz_id = request.json.get('quiz_id', None)
    if quiz_id is None:
        return invalid_json()
    try:
        quiz_info = ops.get_quiz(quiz_id, user_id)
    except NoResultFound:
        return forbidden()
    try:
        get_brightspace().post_quiz(bs_org_unit_id, quiz_info)
    except Exception as e:
        return _forbidden_or_internal_server_error(e)
    return success()


@brightspace_api_blueprint.route(
    'export_grades/courses/<int:bs_org_unit_id>',
    methods=['POST'])
def export_course_quiz_grades(bs_org_unit_id):
    """Exports quiz grades from Heymans to Brightspace.
    
    Request JSON example
    --------------------
    {
        "quiz_id": <int>,
        "grade_name": <str>,
        "grading_formula": "ug_bss" #optional        
    }

    Returns
    -------
    200 OK
    400 Bad Request
    403 Forbidden
    500 Internal Server Error
    """
    user_id = current_user.get_id()
    quiz_id = request.json.get('quiz_id', None)
    grade_name = request.json.get('grade_name', None)
    grading_formula = request.json.get('grading_formula', 'ug_bss')
    if grading_formula not in config.max_points:
        raise invalid_json()
    max_points = config.max_points[grading_formula]
    if quiz_id is None or grade_name is None:
        return invalid_json()
    try:
        quiz_info = ops.get_quiz(quiz_id, user_id)
    except NoResultFound:
        return forbidden()
    # We compile the grade item for the full grade based on the grade report
    grades_dm = report.calculate_grades(quiz_info,
                                        grading_formula=grading_formula)
    grade_item = {
        "name": grade_name,
        "description": "Quiz grade",
        "max_points": max_points,
        "grades": []
    }
    for row in grades_dm:
        grade_item['grades'].append({
            "username": row.username,
            "feedback": "See individual questions for feedback",
            "score": row.score
        })
    grade_items = [grade_item]
    # The grade items for the invidiual scores are compiled separately
    for i, question in enumerate(quiz_info['questions'], start=1):
        grade_item = {
            "name": f'{grade_name} (Q{i})',
            "description": f"Score for question {i}",
            "max_points": 1,
            "grades": []
        }
        for attempt in question['attempts']:            
            grade_item['grades'].append({
                "username": attempt['username'],
                "feedback": report.attempt_feedback(question, attempt),
                "score": attempt['score']
            })
        grade_items.append(grade_item)
    try:
        get_brightspace().post_grades(bs_org_unit_id, grade_items)
    except Exception as e:
        return _forbidden_or_internal_server_error(e)
    return success()


def _forbidden_or_internal_server_error(e):
    if isinstance(e, HTTPError) and e.response.status_code == 403:
        return forbidden()
    return internal_server_error(str(e))