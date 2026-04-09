from flask import Blueprint, request, render_template
import logging
from .. import __version__

logger = logging.getLogger('heymans')
public_blueprint = Blueprint('public', __name__)


@public_blueprint.route('/interactive_quizzes/start/<int:interactive_quiz_id>', methods=['GET'])
def iquiz_session(interactive_quiz_id):
    """Render a public interactive-quiz chat page.

    The page itself starts a quiz-conversation on load.
    """
    username = request.args.get('username', 'anonymous')
    
    return render_template( 
        'iquiz_sess.html',
        interactive_quiz_id=interactive_quiz_id,
        username=username,
        version=__version__,
    )
