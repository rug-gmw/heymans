import logging
from typing import List, Dict, Any
from ..models import db, InteractiveQuiz
from ..schemas import InteractiveQuizSchema

logger = logging.getLogger("heymans")

# Re-use one schema instance for efficiency
interactive_quiz_schema = InteractiveQuizSchema()


def new_interactive_quiz(name: str, document_id: int, user_id: int,
                         public: bool = False) -> int:
    """Adds a new interactive quiz to the database and returns its ID."""
    with db.session.begin():
        quiz = InteractiveQuiz(
            name=name,
            document_id=document_id,
            user_id=user_id,
            public=public,
        )
        db.session.add(quiz)
        db.session.flush()
        # At this point the PK is guaranteed to be assigned
        logger.info(
            "Created interactive quiz %s (document=%s, public=%s) for user %s",
            quiz.interactive_quiz_id,
            document_id,
            public,
            user_id,
        )
        return quiz.interactive_quiz_id


def list_interactive_quizzes(user_id: int) -> List[Dict[str, Any]]:
    """
    Returns all interactive quizzes visible to the given user.

    A quiz is visible when:
      • the user owns it, OR
      • it is marked public.

    Returned structure:
        [{"name": <str>, "quiz_id": <int>}, ...]
    """
    with db.session.begin():
        quizzes = (
            db.session.query(InteractiveQuiz)
            .filter(
                (InteractiveQuiz.user_id == user_id) | (InteractiveQuiz.public.is_(True))
            )
            .order_by(InteractiveQuiz.name)
            .all()
        )
        logger.debug("User %s can see %d interactive quizzes", user_id, len(quizzes))
        return [{"name": quiz.name, "quiz_id": quiz.interactive_quiz_id}
                for quiz in quizzes]


def _get_accessible_quiz(interactive_quiz_id: int, user_id: int) -> InteractiveQuiz:
    """
    Helper that returns a quiz if the user may access it,
    or raises an Exception otherwise.
    """
    quiz: InteractiveQuiz | None = db.session.get(
        InteractiveQuiz, interactive_quiz_id
    )

    if quiz is None:
        raise ValueError(f"InteractiveQuiz {interactive_quiz_id} does not exist")

    if not (quiz.user_id == user_id or quiz.public):
        raise PermissionError("You do not have permission to access this quiz")
    return quiz


def get_interactive_quiz(interactive_quiz_id: int, user_id: int) -> Dict[str, Any]:
    """
    Returns a serialised representation of the quiz.

    Raises
    ------
    ValueError
        If the quiz does not exist.
    PermissionError
        If the user is not allowed to read it.
    """
    with db.session.begin():
        quiz = _get_accessible_quiz(interactive_quiz_id, user_id)
        result = interactive_quiz_schema.dump(quiz)
        logger.debug("Loaded interactive quiz %s for user %s", interactive_quiz_id, user_id)
        return result


def delete_interactive_quiz(interactive_quiz_id: int, user_id: int) -> None:
    """
    Deletes a quiz owned by the current user.

    Raises
    ------
    ValueError
        If the quiz does not exist.
    PermissionError
        If the user is not the owner.
    """
    with db.session.begin():
        quiz = db.session.get(InteractiveQuiz, interactive_quiz_id)
        if quiz is None:
            raise ValueError(f"InteractiveQuiz {interactive_quiz_id} does not exist")
    
        if quiz.user_id != user_id:
            raise PermissionError("Only the owner can delete this quiz")
        db.session.delete(quiz)
        logger.info("Deleted interactive quiz %s by user %s", interactive_quiz_id, user_id)
