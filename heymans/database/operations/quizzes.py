import logging
from ..models import db, NoResultFound, Quiz, Question, Attempt, User
from ..schemas import QuizSchema, QuestionSchema, AttemptSchema
from sqlalchemy.orm.exc import NoResultFound

logger = logging.getLogger('heymans')


def get_or_create(session, model, **kwargs):
    """Get or create a model instance while avoiding duplicate creation."""
    instance = session.query(model).filter_by(**kwargs).one_or_none()
    if instance:
        return instance
    else:
        instance = model(**kwargs)
        session.add(instance)
        return instance


def _get_quiz(quiz_id: int, user_id: int):
    logger.info(f'getting quiz {quiz_id} for user {user_id}')
    try:
        return db.session.query(Quiz).filter_by(
            quiz_id=quiz_id, user_id=user_id).one()
    except NoResultFound:
        raise ValueError(f'no quiz {quiz_id} found for user {user_id}')


def new_quiz(quiz_info: dict, user_id: int) -> int:
    """Creates a new quiz with questions and attempts based on the provided
    quiz_info dict."""
    with db.session.begin():
        quiz = Quiz(name=quiz_info['name'], user_id=user_id)
        db.session.add(quiz)
        for question_info in quiz_info['questions']:
            question = Question(text=question_info['text'],
                                answer_key=question_info['answer_key'],
                                quiz=quiz)
            db.session.add(question)
            for attempt_info in question_info['attempts']:
                user = get_or_create(db.session, User,
                                     username=attempt_info['username'])
                attempt = Attempt(answer=attempt_info['answer'],
                                  question=question,
                                  user=user)
                db.session.add(attempt)
    db.session.commit()
    return quiz.quiz_id


def get_quiz(quiz_id: int, user_id: int) -> dict:
    """Returns all quiz information, including questions and attempts as a 
    nested dict.
    """
    quiz = QuizSchema().dump(_get_quiz(quiz_id, user_id))
    db.session.commit()
    return quiz


def delete_quiz(quiz_id: int, user_id: int):
    """Deletes a quiz"""
    db.session.delete(_get_quiz(quiz_id, user_id))
    db.session.commit()


def list_quizzes(user_id: int) -> list:
    """Returns a list of dict objects, where each dict contains the quiz_id and 
    name for a single quiz.
    """
    all_quizzes = db.session.query(Quiz).filter_by(user_id=user_id).all()
    quizzes_schema = QuizSchema(many=True, only=['quiz_id', 'name'])
    quizzes = quizzes_schema.dump(all_quizzes)
    db.session.commit()
    return quizzes


def update_attempts(attempts: list, user_id: int):
    """Updates attempts based on a list of attempt dicts."""
    with db.session.begin():
        for attempt_dict in attempts:
            attempt_id = attempt_dict['attempt_id']
            attempt = db.session.query(Attempt).get(attempt_id)
            if not attempt:
                logger.warning(f'Missing attempt: {attempt_id}')
                continue
            # Fetch the question associated with the attempt
            question = attempt.question
            if not question:
                logger.warning(f'Missing question for attempt: {attempt_id}')
                continue
            # Fetch the quiz to which the question belongs
            quiz = question.quiz
            if not quiz:
                logger.warning(f'Missing quiz for question ID: {question.question_id}')
                continue
            # Check if the current user owns the quiz
            if quiz.user_id != user_id:
                logger.warning(f'User {user_id} does not own quiz ID: {quiz.quiz_id}')
                continue
            # Update attempt details if the user owns the quiz
            attempt.score = attempt_dict['score']
            attempt.feedback = attempt_dict['feedback']
    db.session.commit()
