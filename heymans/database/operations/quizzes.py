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

def _quiz_name_exists(name: str, user_id: int,
                      exclude_quiz_id: int | None = None) -> bool:
    """Return True if a quiz with the given name exists for the user.

    Parameters
    ----------
    name : str
        The quiz name to check.
    user_id : int
        The owner/user id to scope uniqueness.
    exclude_quiz_id : int or None, optional
        If provided, exclude this quiz id from the existence check.
    """
    query = db.session.query(Quiz.quiz_id).filter(
        Quiz.user_id == user_id,
        Quiz.name == name,
    )
    if exclude_quiz_id is not None:
        query = query.filter(Quiz.quiz_id != exclude_quiz_id)
    return db.session.query(query.exists()).scalar()


def _unique_quiz_name(base_name: str, user_id: int,
                      exclude_quiz_id: int | None = None) -> str:
    """Compute a unique quiz name for a user by appending numeric suffixes.

    Parameters
    ----------
    base_name : str
        Desired base name.
    user_id : int
        The owner/user id to scope uniqueness.
    exclude_quiz_id : int or None, optional
        If provided, exclude this quiz id from the uniqueness check (useful for updates).

    Returns
    -------
    str
        A unique name scoped to the user.
    """
    base = base_name
    candidate = base
    counter = 1
    while _quiz_name_exists(candidate, user_id,
                            exclude_quiz_id=exclude_quiz_id):
        candidate = f"{base} ({counter})"
        counter += 1
    return candidate


def new_quiz(name: str, user_id: int) -> int:
    """Create a new empty quiz with a unique name for the given user.

    Ensures uniqueness by appending a numeric suffix like " (1)", " (2)", etc.,
    when a quiz with the same name already exists for the same user.

    Parameters
    ----------
    name : str
        Desired quiz name.
    user_id : int
        The ID of the user who owns the quiz.

    Returns
    -------
    int
        The primary key (quiz_id) of the newly created quiz.

    Notes
    -----
    - Uniqueness is enforced per user only.
    - All database operations occur within a transaction block.
    """
    with db.session.begin():
        unique_name = _unique_quiz_name(name, user_id)
        quiz = Quiz(name=unique_name, user_id=user_id)
        db.session.add(quiz)
        db.session.flush()
        return quiz.quiz_id


def update_quiz(quiz_id: int, quiz_info: dict, user_id: int) -> None:
    """Replace an existing quiz’s metadata, questions, and attempts.

    Ensures the quiz name remains unique per user. When updating, if the
    requested name equals the current quiz name, it will not be treated as a duplicate.
    Otherwise, a numeric suffix like " (1)", " (2)", etc., is appended until unique.

    Parameters
    ----------
    quiz_id : int
        The primary key of the quiz to update.
    quiz_info : dict
        Structure with updated quiz metadata, questions, and attempts.
    user_id : int
        Owner of the quiz, used to scope uniqueness and authorization.

    Notes
    -----
    - All operations occur within a transaction.
    - Existing questions and attempts are fully replaced.
    """
    with db.session.begin():
        quiz = _get_quiz(quiz_id, user_id)

        # Quiz-level fields
        if 'name' in quiz_info:
            requested_name = quiz_info['name']
            # Only compute a unique name if it differs or conflicts with others
            if requested_name != quiz.name:
                quiz.name = _unique_quiz_name(requested_name, user_id,
                                              exclude_quiz_id=quiz_id)
        if 'validation' in quiz_info:
            quiz.validation = quiz_info['validation']
        else:
            quiz.validation = None

        if 'qualitative_error_analysis' in quiz_info:
            quiz.qualitative_error_analysis = quiz_info['qualitative_error_analysis']
        else:
            quiz.qualitative_error_analysis = None

        # Remove existing questions (cascade deletes attempts if configured)
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
                attempt = Attempt(
                    answer=a_info['answer'],
                    question=question,
                    username=a_info['username'],
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


def update_attempts(quiz_id: int, quiz_data: dict, user_id: int) -> None:
    """Bulk-update attempts based on a list of attempt dicts."""
    attempts = []
    for question in quiz_data['questions']:
        attempts += question['attempts']
    with db.session.begin():
        # First commit the qualitative error analysis
        quiz = _get_quiz(quiz_id, user_id)
        quiz.qualitative_error_analysis = \
            quiz_data.get('qualitative_error_analysis', '')
        # Then commit all attempts
        for a_dict in attempts:
            attempt = db.session.get(Attempt, a_dict['attempt_id'])
            if not attempt:
                logger.warning('Missing attempt: %s', a_dict['attempt_id'])
                continue

            quiz = attempt.question.quiz if attempt.question else None
            if not quiz or quiz.user_id != user_id:
                logger.warning(
                    f'User {user_id} not allowed to edit attempt owned by {quiz.user_id}')
                continue

            attempt.score = a_dict['score']
            if a_dict['feedback'] is not None:
                attempt.feedback = json.dumps(a_dict['feedback'])
