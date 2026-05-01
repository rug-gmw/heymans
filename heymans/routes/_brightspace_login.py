import logging
import time
from flask import redirect, Blueprint, url_for, request, session
from flask_login import login_user
import bsapi
from bsapi import oauth
from .. import config
from . import User


logger = logging.getLogger('heymans')
brightspace_login_blueprint = Blueprint('brightspace_login', __name__)


@brightspace_login_blueprint.route("/login")
def login():
    """Send the user to the Brightspace authorization page.

    Brightspace uses a centralized auth server, so we don't need to know the
    institution-specific LMS URL here.
    """
    auth_url = oauth.create_auth_url(
        config.brightspace_client_id,
        config.brightspace_redirect_uri,
        config.brightspace_scope,
    )
    logger.info('redirecting user to Brightspace authorization page')
    return redirect(auth_url)


@brightspace_login_blueprint.route("/logout")
def logout():
    return redirect(f'https://{config.brightspace_lms_url}/d2l/logout')


@brightspace_login_blueprint.route("/callback")
def callback():
    """Handle Brightspace's redirect after the user authorizes the app.

    Brightspace appends a one-time `?code=...` to the URL; we exchange it for
    an access token, fetch the user's profile to identify them, and log them
    in via Flask-Login.
    """
    # Verify Brightspace returned an authorization code.
    code = request.args.get('code')
    if not code:
        logger.warning('no authorization code returned from Brightspace')
        return redirect(url_for('app.login'))

    try:
        authorization_code = oauth.parse_callback_url(request.url)
    except Exception as e:
        logger.error(f'failed to parse Brightspace callback URL: {e}')
        return redirect(url_for('app.login'))

    # Exchange the authorization code for an access token.
    try:
        token_response = oauth.exchange_code_for_token(
            config.brightspace_client_id,
            config.brightspace_client_secret,
            config.brightspace_redirect_uri,
            authorization_code,
        )
    except Exception as e:
        logger.error(f'failed to exchange Brightspace code for token: {e}')
        return redirect(url_for('app.login'))

    # Use the access token to identify the user.
    try:
        api = bsapi.BSAPI(
            token_response['access_token'], config.brightspace_lms_url
        )
        whoami = api.whoami()
    except Exception as e:
        logger.error(f'failed to fetch Brightspace user info: {e}')
        return redirect(url_for('app.login'))

    unique_id = str(whoami.identifier)
    username = f'{whoami.first_name} {whoami.last_name} ({whoami.unique_name})'
    user_email = 'unknown'  # not available

    if not unique_id:
        logger.warning('Brightspace whoami returned no Identifier; aborting')
        return redirect(url_for('app.login'))

    logger.info(
        f'Brightspace log-in successful ({username}; {user_email}; {unique_id})'
    )
    user = User(unique_id, user_email)
    login_user(user)

    # Store some profile fields in the session for use elsewhere in the app.
    session['name'] = username
    session['email'] = user_email
    session['bs_access_token'] = token_response['access_token']
    session['bs_expires_at'] = time.time() + token_response['expires_in']

    return redirect('/app/quiz')
