import logging
import requests
import json
import base64
from flask import redirect, Blueprint, url_for, request, session
from flask_login import login_user

from .. import config
from . import User

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC # TODO
from cryptography.hazmat.backends import default_backend # TODO
from cryptography.hazmat.primitives import hashes # TODO

from oauthlib.oauth2 import WebApplicationClient

logger = logging.getLogger('heymans')
google_login_blueprint = Blueprint('google_login', __name__)

# make requests to google discovery, interfacing start point:
def get_google_provider_cfg():
    try:
        response = requests.get(config.google_discovery_url, timeout=5)
        response.raise_for_status()  # raises HTTPError for 4xx/5xx
        return response.json()
    except (requests.RequestException, JSONDecodeError) as e:
        logger.error(f"Failed to fetch or parse Google provider config: {e}")
        return None

@google_login_blueprint.route("/")
def login():
    # make a client:
    client = WebApplicationClient(config.google_client_id)
    google_provider_cfg =  get_google_provider_cfg()
    if not google_provider_cfg:
        logger.info("Getting the google client failed. Send user back to login page")
        # TODO: would be nice to have some error message to show?
        return redirect(url_for('app.login'))

    # Now, send the user to a login screen with a redirect callback url:
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # TODO: could be made https here:
    redirect_uri=request.base_url + "callback"
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=redirect_uri,
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)

@google_login_blueprint.route("/callback")
def callback():
    client = WebApplicationClient(config.google_client_id)
    # Get authorization code Google sent back (check if they did)
    code = request.args.get("code")
    if not code:
        logger.warning("No authorization code returned from Google.")
        return redirect(url_for('app.login'))  

    google_provider_cfg = get_google_provider_cfg()
    if not google_provider_cfg:
        logger.info("Getting the google client failed. Send user back to login page")
        # TODO: would be nice to have some error message to show?
        return redirect(url_for('app.login'))

    token_endpoint = google_provider_cfg["token_endpoint"]
    redirect_uri=request.base_url + "callback"

    # Prepare and send a request to get tokens:
    try:
        token_url, headers, body = client.prepare_token_request(
            token_endpoint,
            authorization_response=request.url.replace('http:', 'https:'),
            redirect_url=request.base_url,
            code=code
        )
    except Exception as e:
        # This really shouldn't fail, but who knows...
        logger.error(f'Unexpected error during token preparation: {e}')
        return redirect(url_for('app.login'))

    ## ok, now get a token, and put it in the client:
    
    try:
        token_response = requests.post(
            token_url,
            headers=headers,
            data=body,
            auth=(config.google_client_id, config.google_client_secret),
            timeout=5
        )
        token_response.raise_for_status()
        token_json = token_response.json()
        client.parse_request_body_response(json.dumps(token_json))
    except requests.HTTPError as http_err:
        logger.error(f"HTTP error during token request: {http_err}")
        return redirect(url_for('app.login'))
    except requests.RequestException as req_err:
        logger.error(f"Request failed during token exchange: {req_err}")
        return redirect(url_for('app.login'))
    except ValueError as json_err:
        logger.error(f"Invalid JSON in token response: {json_err}")
        return redirect(url_for('app.login'))
    except Exception as e:
        logger.error(f"Unexpected error during token parsing: {e}")
        return redirect(url_for('app.login'))

    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)

    ### Using the token, we can now get user profile info:
    try:
        userinfo_response = requests.get(uri, headers=headers, data=body, timeout=5)
        userinfo_response.raise_for_status()
        userinfo = userinfo_response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch user info: {e}")
        return redirect(url_for('app.login'))
    except ValueError as e:
        logger.error(f"Failed to parse user info JSON: {e}")
        return redirect(url_for('app.login'))
    if (not userinfo.get("email_verified")) or (not userinfo["email"].endswith("@rug.nl")):
        logger.info("Email not verified or invalid domain: Denying login")
        return redirect('/login_failed') ### TODO doesn't exist

    # get some relevant user-data and log them in:
    unique_id = userinfo["sub"]
    username = userinfo["name"]
    logger.info(f'google log-in successful ({username})')
    user = User(f'{username} (Google)')
    login_user(user)
    session['name'] = username
    session['picture'] = userinfo.get("picture")

    ### make an encryption key:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(),
                     length=32,
                     salt=config.encryption_salt,
                     iterations=100000,
                     backend=default_backend())
    logger.info(f'initializing encryption key')    
    session['encryption_key'] = base64.urlsafe_b64encode(
        kdf.derive(unique_id.encode()))

    return redirect('/app/quiz')

##### TODO: https ??
##### TODO: add a proper redirect URI?
##### TODO: Do something with User: User(Username) doesn't work. Do we go with unique_id?










