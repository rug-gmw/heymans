import json
from http import HTTPStatus
from flask import Blueprint, request, jsonify, make_response, \
    render_template, redirect, url_for, session
from flask_login import current_user, login_user, logout_user, UserMixin
from redis import Redis
import logging
from ..forms import LoginForm

logger = logging.getLogger('heymans')
app_blueprint = Blueprint('app', __name__)


class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id
        logger.info(f'initializing user id: {self.id}')
    
    # TODO: any use that this is an int?
    # def get_id(self):
    #     return int(self.id)

### TODO: get rid of form?
def login_handler(form):
    return render_template('login.html', form=form)

@app_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        logout_user() ### TEMP: for now, in order to keep testing login
        return redirect(url_for('app.quiz'))
    return login_handler(LoginForm())
    
    
@app_blueprint.route('/logout')
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('app.login'))


@app_blueprint.route('/quiz', methods=['GET'])
def quiz():
    """Returns the quiz front-end."""
    if not current_user.is_authenticated:
        return redirect(url_for('app.login'))
    return render_template('quiz.html')
