from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import logging
from . import not_found, no_content
from ..database.operations import qa as qa_ops
from ..database.models import NoResultFound
from .. import config, qa

logger = logging.getLogger('heymans')
qa_api_blueprint = Blueprint('api/qa', __name__)


@qa_api_blueprint.route('/new', methods=['POST'])
@login_required
def new():
    """Create a new Q&A conversation and returns its identifier.

    Request JSON example
    --------------------
    {
        "name": <str>  # optional, defaults to "Q&A Session"
    }
    
    Reply JSON example
    ------------------
    {
        "qa_conversation_id": <int>
    }

    Returns
    -------
    200 OK
    """
    name = request.json.get('name', 'Q&A Session')
    user_id = current_user.get_id()
    qa_conversation_id = qa_ops.new_qa_conversation(name, user_id)
    logger.info(f'created Q&A conversation: {qa_conversation_id}')
    return jsonify({'qa_conversation_id': qa_conversation_id})


@qa_api_blueprint.route('/list')
@login_required
def list_():
    """Return a list of Q&A conversations owned by the current user.
    
    Reply JSON example
    ------------------
    [
        {
            "name": <str>,
            "qa_conversation_id": <int>,
            "created_at": <str>,  # ISO format timestamp
            "updated_at": <str>   # ISO format timestamp
        },
        ...
    ]

    Returns
    -------
    200 OK
    """
    return jsonify(qa_ops.list_qa_conversations(current_user.get_id()))


@qa_api_blueprint.route('/get/<int:qa_conversation_id>')
@login_required
def get(qa_conversation_id):
    """Retrieve full Q&A conversation details.

    Reply JSON example
    ------------------
    {
        "name": <str>,
        "qa_conversation_id": <int>,
        "created_at": <str>,
        "updated_at": <str>,
        "qa_messages": [
            {
                "qa_message_id": <int>,
                "role": <str>,  # "user" or "ai"
                "text": <str>,
                "sources": [  # only present for AI messages
                    {
                        "document_id": <int>,
                        "document_name": <str>,
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
    try:
        qa_conversation = qa_ops.get_qa_conversation(qa_conversation_id, user_id)
    except NoResultFound:
        return not_found("Q&A conversation not found")
    return jsonify(qa_conversation)


@qa_api_blueprint.route('/delete/<int:qa_conversation_id>', methods=['DELETE'])
@login_required
def delete(qa_conversation_id):
    """Delete a Q&A conversation and its associated messages.

    Returns
    -------
    204 No Content
    404 Not Found
    """
    try:
        qa_ops.delete_qa_conversation(qa_conversation_id, current_user.get_id())
    except Exception as e:
        return not_found(str(e))
    logger.info(f'deleted Q&A conversation: {qa_conversation_id}')
    return no_content()


@qa_api_blueprint.route('/send_message/<int:qa_conversation_id>', methods=['POST'])
@login_required
def send_message(qa_conversation_id):
    """Sends a new message to the Q&A conversation and returns the AI reply
    with document sources.
    
    Request JSON example
    --------------------
    {
        "text": <str>,
        "model": <str>,  # optional
        "max_sources": <int>  # optional, defaults to 5
    }
    
    Reply JSON example
    ------------------
    {
        "reply": <str>,
        "sources": [
            {
                "document_id": <int>,
                "document_name": <str>
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
    text = request.json.get('text')
    model = request.json.get('model', config.default_model)
    max_sources = request.json.get('max_sources', config.qa_max_documents)
    
    # Verify user has access to this conversation
    try:
        qa_conversation = qa_ops.get_qa_conversation(qa_conversation_id, user_id)
    except NoResultFound:
        return not_found("Q&A conversation not found")
    
    # Store user message
    qa_ops.new_qa_message(qa_conversation_id, user_id, text, 'user')
    reply_text, sources = qa.get_reply(qa_conversation, model, max_sources)
    
    # Store AI message with sources
    qa_ops.new_qa_message(qa_conversation_id, user_id, reply_text, 'ai',
                          document_ids=None)
    
    return jsonify({
        "reply": reply_text,
        "sources": []
    })
