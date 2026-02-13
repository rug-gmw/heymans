from flask import Blueprint, request, render_template, redirect, url_for, \
    session, current_app
from flask_login import current_user, login_user, logout_user, UserMixin
import logging
from .. import config, __version__
from ..forms import LoginForm
from ..database.operations import users as ops

logger = logging.getLogger('heymans')
app_blueprint = Blueprint('app', __name__)

class User(UserMixin):
    def __init__(self, user_id, email='null@null.com'):
        self.id = user_id
        self.email = email
        logger.info(f'initializing user id: {self.id}')
        ops.create_user_if_not_exists(username=self.email, user_id=self.id)

    def get_id(self):
        return self.id
    
### N.B.: 'form' left in for future use. currently not used.
def login_handler(form):
    return render_template('login.html', form=form, version=__version__)

@app_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    # For unit tests: bypass Google SSO if testing
    if current_app.config.get("TESTING") and request.method == 'POST':
        test_user = User(user_id='dummy', email='test@test.com')
        login_user(test_user)
        return '', 200  # success for the test client

    if current_user.is_authenticated:
        return redirect(url_for('app.quiz'))
    return login_handler(LoginForm())    
    
@app_blueprint.route('/logout')
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('app.login'))

@app_blueprint.route('/quiz', methods=['GET'])
def quiz():
    """Returns the quiz (grading) front-end."""
    if not current_user.is_authenticated:
        return redirect(url_for('app.login'))
    return render_template('quiz.html', showDebugInfo=config.show_debug_info,
                           version=__version__)

@app_blueprint.route('/kb', methods=['GET'])
def kb():
    """Returns the knowledge base front-end."""
    if not current_user.is_authenticated:
        return redirect(url_for('app.login'))
    return render_template('kb.html', showDebugInfo=config.show_debug_info,
                           version=__version__)
