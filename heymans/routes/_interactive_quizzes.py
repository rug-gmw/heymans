from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import logging
from . import not_found, no_content
from ..database.operations import documents as doc_ops, \
    interactive_quizzes as iq_ops
from ..database.models import NoResultFound
from .. import interactive_quizzes as iq, config

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
    
    Reply JSON example
    ------------------
    {
        "interactive_quiz_id": <int>
    }

    Returns
    -------
    200 OK
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
    
    Reply JSON example
    ------------------
    [
        {
            "name": <str>,
            "interactive_quiz_id": <int>
        },
        ...
    ]

    Returns
    -------
    200 OK
    """
    return jsonify(iq_ops.list_interactive_quizzes(current_user.get_id()))

    
@iq_api_blueprint.route('/get/<int:interactive_quiz_id>')
@login_required
def get(interactive_quiz_id):
    """Retrieve full quiz interactive details and results.

    Reply JSON example
    ------------------
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
    404 Not Found
    """
    user_id = current_user.get_id()
    try:
        iq = iq_ops.get_interactive_quiz(interactive_quiz_id, user_id)
    except NoResultFound:
        return not_found("Interactive quiz not found")
    for conversation in iq['conversations']:
        del conversation['chunks']
        del conversation['messages']
    return jsonify(iq)


@iq_api_blueprint.route('/delete/<int:interactive_quiz_id>',
                        methods=['DELETE'])
@login_required
def delete(interactive_quiz_id):
    """Delete an interactive quiz and it's associated data.

    Returns
    -------
    204 No Content
    404 Not Found
    """
    try:
        iq_ops.delete_interactive_quiz(interactive_quiz_id,
                                       current_user.get_id())
    except Exception as e:
        return not_found(str(e))
    return no_content()


@iq_api_blueprint.route('/conversation/start/<int:interactive_quiz_id>',
                        methods=['GET'])
@login_required
def conversation_start(interactive_quiz_id):
    """Starts a new conversation for the current user.
    
    Reply JSON example
    ------------------
    {
        "conversation_id": <int>
    }
    
    Returns
    -------
    200 OK
    404 Not Found
    """
    user_id = current_user.get_id()
    try:
        conversation_id = iq_ops.new_interactive_quiz_conversation(
            interactive_quiz_id, user_id)
    except Exception as e:
        return not_found(str(e))
    return jsonify({"conversation_id": conversation_id})


@iq_api_blueprint.route('/conversation/send_message/<int:conversation_id>',
                        methods=['POST'])
@login_required
def conversation_send_message(conversation_id):
    """Sends a new message to the conversation, and returns the heymans reply.
    
    Request JSON example
    --------------------
    {
        "text": <str>,
        "model": <str>  # optional
    }
    
    Reply JSON example
    ------------------
    {
         "reply": <str>,
         "finished": <bool>
    }
    
    Returns
    -------
    200 OK
    404 Not Found
    """    
    user_id = current_user.get_id()
    text = request.json.get('text')
    model = request.json.get('model', config.default_model)
    try:
        iq_ops.new_interactive_quiz_message(
            conversation_id, user_id, text, 'user')
    except Exception as e:
        return not_found(str(e))
    conversation = iq_ops.get_interactive_quiz_conversation(conversation_id,
                                                            user_id)
    reply_text, finished = iq.get_reply(conversation, model)
    iq_ops.new_interactive_quiz_message(
        conversation_id, user_id, reply_text, 'ai')    
    iq_ops.finish_interactive_quiz_conversation(conversation_id, user_id,
                                                finished)
    return jsonify({"reply": reply_text, "finished": finished})
