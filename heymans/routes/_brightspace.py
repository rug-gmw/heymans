import json
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import logging
from . import missing_file, error, success, not_found
from ..database.operations import documents as ops

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
    400 Bad Request
    """
    pass
    

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
    400 Bad Request
    """
    pass


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
    400 Bad Request
    """
    pass


@brightspace_api_blueprint.route(
    '/export/courses/<int:bs_org_unit_id>/quizzes',
    methods=['POST'])
@login_required    
def export_course_quiz(bs_org_unit_id, quiz_id):
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
    """    
    pass


@brightspace_api_blueprint.route(
    'export_grades/courses/<int:bs_org_unit_id>',
    methods=['POST'])
def export_course_quiz_grades(bs_org_unit_id):
    """Exports quiz grades from Heymans to Brightspace.
    
    Request JSON example
    --------------------
    {
        "quiz_id": <int>,
        "grade_name": <str>
    }

    Returns
    -------
    200 OK
    400 Bad Request
    """
    pass
