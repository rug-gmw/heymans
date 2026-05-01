"""Brightspace API client for the Heymans Flask app.

The Flask app handles the OAuth login flow elsewhere and stores the access
token (plus its absolute expiry timestamp) in the user's session. This module
provides:

  - `Brightspace`: a thin, Flask-agnostic wrapper around `bsapi.BSAPI` that
    exposes the high-level operations Heymans needs.
  - `get_brightspace()`: a Flask helper that constructs a `Brightspace` from
    the current session, raising `BrightspaceLoginRequired` if no valid token
    is available.
  - `brightspace_login_required`: a decorator for Flask routes that redirects
    to the login flow when no valid token is available.
"""
import re
import time
import bsapi
from flask import session
from . import config
import logging
logger = logging.getLogger('heymans')


CUSTOM_API_VERSION = '1.0'


class BrightspaceLoginRequired(Exception):
    """Raised when no valid Brightspace token is available in the session."""


class Brightspace:
    """A Flask-agnostic Brightspace client.

    Instantiate with an access token and LMS URL; if the token expires the
    caller is expected to redirect the user back through the OAuth flow.
    """

    def __init__(self, access_token: str, lms_url: str):
        self.access_token = access_token
        self.lms_url = lms_url
        self._api = bsapi.BSAPI(access_token, lms_url)

    # ---- Internal helpers ------------------------------------------------

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Lowercase + alphanumeric-only, for robust question-text matching."""
        return re.sub(r'[^a-z0-9]', '', (text or '').lower())

    @staticmethod
    def _parse_answer_key(answer_key_text: str) -> list:
        """Split a bullet-pointed answer-key string ('- ' separators) into a
        list of individual answer-key items.
        """
        if not answer_key_text:
            return []
        parts = [p.strip() for p in answer_key_text.split('- ')]
        return [p for p in parts if p]

    def _get_user_id_to_username_map(self, org_id: int) -> dict:
        """Fetch the course classlist and return a {Identifier: Username} map
        so we can translate Brightspace user ids to student numbers.
        """
        enrollments = self._api._get_json(
            self._api._get_le_route(f'{org_id}/classlist/'))
        logger.info(f'fetched {len(enrollments)} enrollments for org {org_id}')
        return {user['Identifier']: user['Username'] for user in enrollments}

    # ---- Public API ------------------------------------------------------

    def get_quiz_info(self, org_id: int, quiz_id: int) -> dict:
        """Fetch all questions and (if available) attempts for a quiz and
        merge them into a single dict using the Heymans quiz-info structure.
        """
        logger.info(f'fetching quiz info for quiz {quiz_id} in org {org_id}')

        # 1. Look up the quiz (to get its name)
        quizzes = self._api._get_json(
            self._api._get_le_route(f'{org_id}/quizzes/'))
        quiz = next(
            (q for q in quizzes['Objects'] if q['QuizId'] == quiz_id), None)
        if quiz is None:
            raise ValueError(f'Quiz {quiz_id} not found in org {org_id}.')
        logger.info(f'found quiz "{quiz["Name"]}"')

        # 2. Build the user_id -> studentnumber map from the classlist
        user_id_to_username = self._get_user_id_to_username_map(org_id)

        # 3. Fetch all questions and build the per-question output skeleton
        questions_data = self._api._get_json(
            self._api._get_le_route(f'{org_id}/quizzes/{quiz_id}/questions/'))
        logger.info(f'fetched {len(questions_data["Objects"])} questions')

        norm_text_to_qid = {}
        questions_output = {}  # keyed by QuestionId, preserving insertion order

        for q in questions_data['Objects']:
            qid = q['QuestionId']
            question_text = q['QuestionText']['Text']
            norm = self._normalize_text(question_text)

            if norm in norm_text_to_qid:
                other = questions_output[norm_text_to_qid[norm]]['name']
                raise ValueError(
                    f'Cannot match attempts unambiguously: questions '
                    f'"{q["Name"]}" and "{other}" have effectively identical '
                    f'question text after normalization.')
            norm_text_to_qid[norm] = qid

            answer_key_text = (q.get('QuestionInfo', {})
                                .get('AnswerKey', {})
                                .get('Text', ''))

            questions_output[qid] = {
                'name': q['Name'],
                'text': question_text,
                'answer_key': self._parse_answer_key(answer_key_text),
                'attempts': []
            }

        # 4. Fetch attempts; for each unique user with a completed attempt,
        #    fetch their last attempt and attach responses to the right question
        attempts_data = self._api._get_json(
            self._api._get_le_route(f'{org_id}/quizzes/{quiz_id}/attempts/'))
        logger.info(
            f'fetched {len(attempts_data["Objects"])} attempt records')

        seen_users = set()
        for attempt in attempts_data['Objects']:
            if attempt.get('Completed') is None:
                continue  # skip in-progress attempts
            user_id = attempt['UserId']
            if user_id in seen_users:
                continue  # 'lastquizattempt' is per-user; one call is enough
            seen_users.add(user_id)

            username = user_id_to_username.get(user_id)
            if username is None:
                logger.warning(
                    f'no classlist entry for user {user_id}; '
                    f'falling back to user id as username')
                username = str(user_id)

            last_attempt = self._api._get_json(
                f'/d2l/api/customization/{CUSTOM_API_VERSION}'
                f'/quizzes/{org_id}/{quiz_id}/lastquizattempt/{user_id}')

            for response in last_attempt.get('Responses', []):
                norm = self._normalize_text(response.get('QuestionText', ''))
                qid = norm_text_to_qid.get(norm)
                if qid is None:
                    raise ValueError(
                        f'No matching question found for response with text: '
                        f'"{response.get("QuestionText", "")[:80]}..." '
                        f'(user {user_id}).')

                questions_output[qid]['attempts'].append({
                    'username': username,
                    'answer': response.get('TextResponse', '') or ''
                })

        logger.info(
            f'merged responses from {len(seen_users)} users into '
            f'{len(questions_output)} questions')

        return {
            'name': quiz['Name'],
            'quiz_id': quiz_id,
            'questions': list(questions_output.values())
        }


# ---- Flask integration ---------------------------------------------------

def get_brightspace() -> Brightspace:
    """Build a `Brightspace` from the current Flask session.

    Raises `BrightspaceLoginRequired` if no token is in the session or the
    stored token has expired.
    """
    access_token = session.get('bs_access_token')
    expires_at = session.get('bs_expires_at', 0)
    if not access_token or time.time() >= expires_at:
        # Drop any stale tokens so we don't keep retrying with them
        session.pop('bs_access_token', None)
        session.pop('bs_expires_at', None)
        logger.info('no valid brightspace token in session')
        raise BrightspaceLoginRequired()
    return Brightspace(access_token, config.brightspace_lms_url)
