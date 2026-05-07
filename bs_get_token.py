"""
One-shot helper: log into Brightspace via OAuth 2.0 and save the resulting
*refresh token* to a JSON file, so unit tests can mint fresh access tokens
without a human in the loop.

Usage:
    python bs_get_token.py

A browser tab will open the Brightspace login page (via Flask on
https://127.0.0.1:5000). After you log in and consent, the refresh token is
written to ``.bs_token.json`` and this script exits automatically.

Re-run this script whenever the refresh token has expired or been revoked
(typically every few weeks/months).

Requires: flask, bsapi, python-dotenv, cryptography (for ssl_context='adhoc').
Reads BRIGHTSPACE_* variables from .env.
"""
import json
import os
import threading
from pathlib import Path
from bsapi import oauth
from dotenv import load_dotenv
from flask import Flask, redirect, request

load_dotenv()

# --- Config from .env --------------------------------------------------------
CLIENT_ID     = os.environ['BRIGHTSPACE_CLIENT_ID']
CLIENT_SECRET = os.environ['BRIGHTSPACE_CLIENT_SECRET']
REDIRECT_URI  = os.environ['BRIGHTSPACE_REDIRECT_URI']
SCOPE         = os.environ['BRIGHTSPACE_SCOPE']
LMS_URL       = os.environ['BRIGHTSPACE_LMS_URL']

TOKEN_FILE = Path('.bs_token.json')

# --- Flask app ---------------------------------------------------------------
app = Flask(__name__)
app.secret_key = 'not-used-but-flask-wants-one'


@app.route('/')
def index():
    """Redirect straight to Brightspace login — no UI needed."""
    return redirect(oauth.create_auth_url(CLIENT_ID, REDIRECT_URI, SCOPE))


@app.route('/brightspace_login/callback')
def brightspace_callback():
    """Exchange the one-time code for tokens, save refresh token, exit."""
    authorization_code = oauth.parse_callback_url(request.url)
    token_response = oauth.exchange_code_for_token(
        CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, authorization_code
    )

    payload = {
        'refresh_token': token_response['refresh_token'],
        'client_id':     CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'lms_url':       LMS_URL,
    }
    TOKEN_FILE.write_text(json.dumps(payload, indent=2))
    print(f'Refresh token saved to {TOKEN_FILE.resolve()}')

    # Give Flask half a second to flush the response to the browser, then exit.
    threading.Timer(0.5, lambda: os._exit(0)).start()

    return (
        '<h1>&#x2705; Refresh token saved</h1>'
        f'<p>Written to <code>{TOKEN_FILE}</code>. You can close this tab.</p>'
    )


if __name__ == '__main__':
    print('Open https://127.0.0.1:5000 in your browser to log in.')
    app.run(host='127.0.0.1', port=5000, ssl_context='adhoc', debug=False)
