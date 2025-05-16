from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import logging
from . import not_found, no_content
from ..database.operations import documents as doc_ops, \
    interactive_quizzes as iq_ops
from ..database.models import NoResultFound

logger = logging.getLogger('heymans')
iq_api_blueprint = Blueprint('api/interactive_quizzes', __name__)


@iq_api_blueprint.route('/new', methods=['POST'])
@login_required
def new():
    """Create a new (empty) interactive quiz and returns its identifier.

    Request JSON example
    --------------------
    {
        "name": <str>,
        "document_id": <int>,
        "public": <bool>
    }

    Returns
    -------
    200 OK
        JSON: {"quiz_id": <int>}
    """
    name = request.json.get('name')
    document_id = request.json.get('document_id')
    public = request.json.get('public')
    user_id = current_user.get_id()
    if not doc_ops.has_access(user_id, document_id):
        return not_found()
    interactive_quiz_id = iq_ops.new_interactive_quiz(name, document_id, user_id, public)
    logger.info(f'created interactive quiz: {interactive_quiz_id}')
    return jsonify({'interactive_quiz_id': interactive_quiz_id})
    

@iq_api_blueprint.route('/list')
@login_required
def list_():
    """Return a list of interactive quizzes owned by the current user.

    Returns
    -------
    200 OK
        JSON: [{"name": <str>, "interactive_quiz_id": <int>}, ...]
    """
    return jsonify(iq_ops.list_interactive_quizzes(current_user.get_id()))

    
@iq_api_blueprint.route('/get/<int:interactive_quiz_id>')
@login_required
def get(interactive_quiz_id):
    """Retrieve full quiz interactive details and results.

    JSON schema
    -----------
    {
        "name": <str>,
        "document_id": <int>,
        "interactive_quiz_id": <int>,
        "conversations": [
            {
                "user_id": <int>,
                "finished": <bool>
            },
            ...     
        ]
    }

    Returns
    -------
    200 OK
        Interactive quiz data as shown above.
    404 Not Found
        Quiz not found.
    """
    user_id = current_user.get_id()
    try:
        return jsonify(iq_ops.get_interactive_quiz(interactive_quiz_id, user_id))
    except NoResultFound:
        return not_found("Interactive quiz not found")


@iq_api_blueprint.route('/delete/<int:interactive_quiz_id>',
                        methods=['DELETE'])
@login_required
def delete(interactive_quiz_id):
    """Delete an interactive quiz and it's associated data.

    Returns
    -------
    204 No Content
        Interactive quiz successfully deleted.
    404 Not Found
        Interactive quiz not found.
    """
    try:
        iq_ops.delete_interactive_quiz(interactive_quiz_id,
                                       current_user.get_id())
    except Exception as e:
        return not_found(str(e))
    return no_content()


def start():
    pass    

        
def stream():
    pass
