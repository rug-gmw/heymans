import json
from http import HTTPStatus
from flask import Blueprint, request, jsonify, make_response, \
    render_template, redirect, url_for
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
    
    def get_id(self):
        return int(self.id)


def login_handler(form):
    if form.validate_on_submit():
        username = form.username.data.strip().lower()
        password = form.password.data.strip()
        user = User(username)
        login_user(user)
        logger.info('logged in')
        return redirect(url_for('app.quiz'))
    logger.info('showing log-in screen')
    return render_template('login.html', form=form)


@app_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('app.quiz'))
    return login_handler(LoginForm())
    
    
@app_blueprint.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('app.login'))


@app_blueprint.route('/quiz', methods=['GET'])
def quiz():
    """Returns the quiz front-end."""
    if not current_user.is_authenticated:
        return redirect(url_for('app.login'))
    return render_template('quiz.html')
