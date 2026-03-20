from flask import Blueprint, request, render_template, redirect, url_for, \
    session, current_app
from flask_login import current_user, login_user, logout_user, UserMixin
import logging
from .. import config, __version__
from ..forms import LoginForm
from ..database.operations import users as ops

logger = logging.getLogger('heymans')
public_blueprint = Blueprint('public', __name__)


@public_blueprint.route('/interactive_quizzes/session/<int:conversation_id>', methods=['GET'])
def iquiz_session(conversation_id):
    """Used to render a chat page, via a custom token."""
    token = request.args.get('token')
    reply = request.args.get('reply', '')
    return render_template(
        'iquiz_sess.html',
        conversation_id=conversation_id,
        token=token,
        initial_reply=reply,
        version=__version__,
    )