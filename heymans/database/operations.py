import logging
from .models import db, NoResultFound, Quiz, Question, Attempt, User
from .schemas import QuizSchema, QuestionSchema, AttemptSchema

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


def new_quiz(quiz_info: dict) -> int:
    """Creates a new quiz with questions and attempts based on the provided
    quiz_info dict."""
    with db.session.begin():
        quiz = Quiz(name=quiz_info['name'])
        db.session.add(quiz)
        for question_info in quiz_info['questions']:
            question = Question(text=question_info['question'],
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


def get_quiz(quiz_id: int) -> dict:
    """Returns all quiz information, including questions and attempts as a 
    nested dict.
    """
    quiz = db.session.query(Quiz).filter_by(quiz_id=quiz_id).one()
    result = QuizSchema().dump(quiz)
    db.session.commit()
    return result


def list_quizzes() -> list:
    """Returns a list of dict objects, where each dict contains the quiz_id and 
    name for a single quiz.
    """
    all_quizzes = db.session.query(Quiz).all()
    quizzes_schema = QuizSchema(many=True, only=['quiz_id', 'name'])
    quizzes = quizzes_schema.dump(all_quizzes)
    db.session.commit()
    return quizzes


def update_attempts(attempts: list):
    """Updates attempts based on a list of attempt dicts."""
    with db.session.begin():
        for attempt_dict in attempts:
            attempt_id = attempt_dict['attempt_id']
            attempt = db.session.query(Attempt).get(attempt_id)
            if not attempt:
                logger.warning(f'missing attempt: {attempt_id}')
                continue
            attempt.score = attempt_dict['score']
            attempt.feedback = attempt_dict['feedback']
    db.session.commit()
