import logging
import json
from ..models import db, Quiz, Question, Attempt, User
from ..schemas import QuizSchema

logger = logging.getLogger('heymans')


def get_or_create(session, model, **kwargs):
    """Get or create a model instance while avoiding duplicate creation."""
    instance = session.query(model).filter_by(**kwargs).one_or_none()
    if instance:
        return instance
    instance = model(**kwargs)
    session.add(instance)
    return instance


def _get_quiz(quiz_id: int, user_id: int):
    """Return the Quiz instance or raise ValueError if it doesn’t exist / is
    not owned by *user_id*.  NOTE: caller is expected to be inside a session
    scope already.
    """
    logger.info('getting quiz %s for user %s', quiz_id, user_id)
    quiz = (
        db.session.query(Quiz)
        .filter_by(quiz_id=quiz_id, user_id=user_id)
        .one_or_none()
    )
    if quiz is None:
        raise ValueError(f'no quiz {quiz_id} found for user {user_id}')
    return quiz


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------

def new_quiz(name: str, user_id: int) -> int:
    """Create a new empty quiz and return its primary key."""
    with db.session.begin():
        quiz = Quiz(name=name, user_id=user_id)
        db.session.add(quiz)
        db.session.flush()
        return quiz.quiz_id


def update_quiz(quiz_id: int, quiz_info: dict, user_id: int) -> None:
    """Replace an existing quiz’s metadata, questions, and attempts.

    All existing questions & attempts are deleted and recreated from the
    supplied *quiz_info* structure.
    """
    with db.session.begin():
        quiz = _get_quiz(quiz_id, user_id)

        # Quiz-level fields
        if 'name' in quiz_info:
            quiz.name = quiz_info['name']
        if 'validation' in quiz_info:
            quiz.validation = quiz_info['validation']

        # Remove existing questions (cascade deletes attempts)
        for question in list(quiz.questions):
            db.session.delete(question)

        # Add new questions & attempts
        for q_info in quiz_info['questions']:
            question = Question(
                text=q_info['text'],
                name=q_info['name'],
                answer_key=json.dumps(q_info['answer_key']),
                quiz=quiz,
            )
            db.session.add(question)

            for a_info in q_info.get('attempts', []):
                user = get_or_create(db.session, User, username=a_info['username'])
                attempt = Attempt(
                    answer=a_info['answer'],
                    question=question,
                    user=user,
                )
                db.session.add(attempt)


def get_quiz(quiz_id: int, user_id: int) -> dict:
    """Return full quiz information (questions + attempts) as a dict."""
    with db.session.begin():
        quiz_dict = QuizSchema().dump(_get_quiz(quiz_id, user_id))

    # Unpack JSON columns outside the TX scope (pure Python work)
    for question in quiz_dict['questions']:
        question['answer_key'] = json.loads(question['answer_key'])
        for attempt in question.get('attempts', []):
            if attempt['feedback'] is not None:
                attempt['feedback'] = json.loads(attempt['feedback'])
    return quiz_dict


def delete_quiz(quiz_id: int, user_id: int) -> None:
    """Delete a quiz (and cascaded children)."""
    with db.session.begin():
        db.session.delete(_get_quiz(quiz_id, user_id))


def list_quizzes(user_id: int) -> list:
    """Return ``[{quiz_id, name}, …]`` for all quizzes owned by *user_id*."""
    with db.session.begin():
        all_quizzes = db.session.query(Quiz).filter_by(user_id=user_id).all()
        quizzes = QuizSchema(many=True, only=['quiz_id', 'name']).dump(all_quizzes)
    return quizzes


def update_attempts(quiz_data: dict, user_id: int) -> None:
    """Bulk-update attempts based on a list of attempt dicts."""
    attempts = []
    for question in quiz_data['questions']:
        attempts += question['attempts']
    with db.session.begin():
        for a_dict in attempts:
            attempt = db.session.get(Attempt, a_dict['attempt_id'])
            if not attempt:
                logger.warning('Missing attempt: %s', a_dict['attempt_id'])
                continue

            quiz = attempt.question.quiz if attempt.question else None
            if not quiz or quiz.user_id != user_id:
                logger.warning(
                    'User %s not allowed to edit attempt %s',
                    user_id,
                    a_dict['attempt_id'],
                )
                continue

            attempt.score = a_dict['score']
            if a_dict['feedback'] is not None:
                attempt.feedback = json.dumps(a_dict['feedback'])
