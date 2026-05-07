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

# OrgUnit Type Id for "Course Offering" in Brightspace's standard taxonomy.
# Used to filter `enrollments/myenrollments/` results so we don't get
# Organizations, Departments, Faculties, or Groups in the courses listing.
ORG_UNIT_TYPE_COURSE_OFFERING = 3


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

    def _get_user_id_to_username_map(self, org_unit_id: int) -> dict:
        """Fetch the (paged) course classlist and return a
        {Identifier: Username} map so we can translate Brightspace user ids
        to student numbers.
        """
        enrollments = self._api.get_classlist_paged(org_unit_id)
        logger.info(f'fetched {len(enrollments)} enrollments for org {org_unit_id}')
        return {user.identifier: user.username for user in enrollments}

    # ---- Public API ------------------------------------------------------

    def list_courses(self) -> list:
        """List the course offerings the current user is enrolled in.

        Calls `GET /d2l/api/lp/<ver>/enrollments/myenrollments/` (paginated
        via the `Items` / `PagingInfo.Bookmark` mechanism) and filters the
        result to OrgUnit type "Course Offering" so that Organization,
        Department, Faculty and Group enrollments are excluded.

        Returns
        -------
        list of dict
            One dict per enrolled course, in the order returned by the API:

            [
                {
                    "name": "Thinking and Deciding",
                    "code": "PSMIN22",
                    "bs_org_unit_id": 12345
                },
                ...
            ]
        """
        items = self._api._get_paged_set(
            self._api._get_lp_route('enrollments/myenrollments/'),
            {'orgUnitTypeId': ORG_UNIT_TYPE_COURSE_OFFERING}
        )
        logger.info(f'fetched {len(items)} course enrollments')
        return [
            {
                'name': item['OrgUnit']['Name'],
                'code': item['OrgUnit']['Code'],
                'bs_org_unit_id': item['OrgUnit']['Id'],
            }
            for item in items
        ]

    def list_course_quizzes(self, org_unit_id: int) -> list:
        """List the quizzes that exist in a given course offering.

        Calls `GET /d2l/api/le/<ver>/<org_unit_id>/quizzes/` (paginated via
        the `Objects` / `Next` mechanism) and returns a minimal projection
        that's convenient for building a "pick a quiz" UI.

        Parameters
        ----------
        org_unit_id : int
            The Brightspace OrgUnit id of the course (as returned by
            `list_courses` under the `bs_org_unit_id` key).

        Returns
        -------
        list of dict
            One dict per quiz, in the order returned by the API:

            [
                {
                    "name": "Practice exam",
                    "bs_quiz_id": 12344
                },
                ...
            ]
        """
        objects = self._api._get_paged(
            self._api._get_le_route(f'{org_unit_id}/quizzes/'))
        logger.info(
            f'fetched {len(objects)} quizzes for org {org_unit_id}')
        return [
            {
                'name': quiz['Name'],
                'bs_quiz_id': quiz['QuizId'],
            }
            for quiz in objects
        ]

    def get_quiz(self, org_unit_id: int, quiz_id: int) -> dict:
        """Fetch all questions and (if available) attempts for a quiz and
        merge them into a single dict using the Heymans quiz-info structure.

        All list-style endpoints (quizzes, questions, attempts, classlist)
        are fetched using the paged helpers, so courses/quizzes that exceed
        a single API page are handled transparently.
        """
        logger.info(f'fetching quiz info for quiz {quiz_id} in org {org_unit_id}')

        # 1. Look up the quiz (to get its name)
        quizzes = self._api._get_paged(
            self._api._get_le_route(f'{org_unit_id}/quizzes/'))
        quiz = next((q for q in quizzes if q['QuizId'] == quiz_id), None)
        if quiz is None:
            raise ValueError(f'Quiz {quiz_id} not found in org {org_unit_id}.')
        logger.info(f'found quiz "{quiz["Name"]}"')

        # 2. Build the user_id -> studentnumber map from the classlist
        user_id_to_username = self._get_user_id_to_username_map(org_unit_id)

        # 3. Fetch all questions and build the per-question output skeleton
        questions = self._api._get_paged(
            self._api._get_le_route(
                f'{org_unit_id}/quizzes/{quiz_id}/questions/'))
        logger.info(f'fetched {len(questions)} questions')

        norm_text_to_qid = {}
        questions_output = {}  # keyed by QuestionId, preserving insertion order

        for q in questions:
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
        attempts = self._api._get_paged(
            self._api._get_le_route(
                f'{org_unit_id}/quizzes/{quiz_id}/attempts/'))
        logger.info(f'fetched {len(attempts)} attempt records')

        seen_users = set()
        for attempt in attempts:
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
                f'/quizzes/{org_unit_id}/{quiz_id}/lastquizattempt/{user_id}')

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

    def post_grades(self, org_unit_id: int, grades: dict) -> None:
        """
        Grades is a dict structured as follows. Here, username corresponds to the
        username in Brightspace, which needs to be mapped onto the userId 
        following a similar logic as above.
        {
            "grade_name": [
                {
                    "username": "s12345678",
                    "feedback": "Some feedback",
                    "score": 10
                },
                ...
            ],
            ...            
        }
        """
        pass  # broken for now
        # for grade_name, grade_data in grades.items():
            # grade_object = self._api._post(
                # self._api._get_le_route(f'{org_unit_id}/grades/'),
                # json={'Name': grade_name}
            # )
            # grade_object_id = grade_object.get('Id')
            # for grade in grade_data:
                # user_id = self._get_user_id(grade['username'])
                # self._api._set_grade_value_numeric(org_unit_id, grade_object_id,
                                                   # user_id, grade['score'],
                                                   # grade['feedback'])
    

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