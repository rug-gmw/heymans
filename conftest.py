"""Pytest fixtures for tests that need a live Brightspace client.

The flow is:

1. Run ``python bs_get_token.py`` once. It opens a browser, you log in, and
   it writes ``.bs_token.json`` with a long-lived refresh token plus the
   client credentials and LMS URL.
2. Run ``pytest`` as usual. The session-scoped ``brightspace`` fixture below
   reads ``.bs_token.json``, exchanges the refresh token for a fresh access
   token, persists any rotated refresh token back to the file, and yields a
   ready-to-use ``heymans.brightspace.Brightspace`` instance.

If the refresh token has been revoked or has finally expired (typically
weeks-to-months after the last login), the fixture fails with a clear message
telling you to re-run ``bs_get_token.py``.
"""
import json
from pathlib import Path

import pytest
from bsapi import oauth

from heymans.brightspace import Brightspace

TOKEN_FILE = Path(__file__).parent / '.bs_token.json'


@pytest.fixture(scope='session')
def brightspace():
    """Yield a `Brightspace` client authenticated via the saved refresh token.

    Session-scoped because access tokens are valid for ~1 hour, which is
    comfortably longer than any sensible test run, so one token per pytest
    invocation is plenty.
    """
    if not TOKEN_FILE.exists():
        pytest.fail(
            f'No {TOKEN_FILE.name} found. Run `python bs_get_token.py` '
            f'once to log into Brightspace and create it.')

    saved = json.loads(TOKEN_FILE.read_text())

    try:
        token_response = oauth.refresh_access_token(
            saved['client_id'],
            saved['client_secret'],
            saved['refresh_token'],
        )
    except Exception as e:
        pytest.fail(
            f'Failed to refresh Brightspace access token ({e!r}). '
            f'The saved refresh token has probably expired or been revoked; '
            f're-run `python bs_get_token.py` to get a new one.')

    # Brightspace may rotate the refresh token. If so, persist the new one
    # so the next test run still works.
    new_refresh = token_response.get('refresh_token')
    if new_refresh and new_refresh != saved['refresh_token']:
        saved['refresh_token'] = new_refresh
        TOKEN_FILE.write_text(json.dumps(saved, indent=2))

    yield Brightspace(token_response['access_token'], saved['lms_url'])
