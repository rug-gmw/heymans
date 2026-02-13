import logging
from typing import List, Dict, Any
from ..models import db, InteractiveQuiz, InteractiveQuizConversation, \
    InteractiveQuizMessage
from ..schemas import InteractiveQuizSchema, InteractiveQuizConversationSchema

logger = logging.getLogger("heymans")

# Re-use one schema instance for efficiency
interactive_quiz_schema = InteractiveQuizSchema()
interactive_quiz_conversation_schema = InteractiveQuizConversationSchema()


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
        quiz = _get_quiz(interactive_quiz_id, user_id)
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
        quiz = _get_quiz(interactive_quiz_id, user_id)    
        if quiz.user_id != user_id:
            raise PermissionError("Only the owner can delete this quiz")
        db.session.delete(quiz)
        logger.info("Deleted interactive quiz %s by user %s", interactive_quiz_id, user_id)


def new_interactive_quiz_conversation(interactive_quiz_id: int,
                                      username: str) -> int:
    """Adds a new interactive quiz conversation to the database and returns its 
    ID. A conversation can be started by any user.
    """
    with db.session.begin():
        _get_quiz(interactive_quiz_id)  # Check if quiz exists
        conversation = InteractiveQuizConversation(
            interactive_quiz_id=interactive_quiz_id,
            username=username)
        db.session.add(conversation)
        db.session.flush()
        logger.info(f"New InteractiveQuizConversation {conversation.conversation_id}")
        return conversation.conversation_id
        
    
def finish_interactive_quiz_conversation(conversation_id: int,
                                         finished: bool = True) -> None:
    """Marks a conversation as finished."""
    with db.session.begin():
        conversation = _get_conversation(conversation_id)
        conversation.finished = finished
        

def get_interactive_quiz_conversation(conversation_id: int) -> dict:
    """Returns a conversation."""
    with db.session.begin():
        conversation = _get_conversation(conversation_id)
        return interactive_quiz_conversation_schema.dump(conversation)


def new_interactive_quiz_message(conversation_id: int, text: str,
                                 message_type: str) -> int:
    """Adds a new interactive quiz message to the database and returns its ID."""
    with db.session.begin():
        _get_conversation(conversation_id)  # Check access
        message = InteractiveQuizMessage(
            conversation_id=conversation_id,
            text=text,
            message_type=message_type)
        db.session.add(message)
        db.session.flush()
        logger.info(f"New InteractiveQuizMessage {message.message_id}")
        return message.message_id
        

## Helpers


def _get_quiz(interactive_quiz_id: int,
              user_id: int | None = None) -> InteractiveQuiz:
    """Helper that returns a quiz if the user may access it, or raises an 
    Exception otherwise. If user_id is None, permission are not checked.
    """
    quiz: InteractiveQuiz | None = db.session.get(
        InteractiveQuiz, interactive_quiz_id
    )
    if quiz is None:
        raise ValueError(f"InteractiveQuiz {interactive_quiz_id} does not exist")    
    if not (user_id is None or quiz.user_id == user_id or quiz.public):
        raise PermissionError("You do not have permission to access this quiz")
    return quiz
    

def _get_conversation(conversation_id: int) -> InteractiveQuizConversation:
    conversation: InteractiveQuizConversation | None = db.session.get(
        InteractiveQuizConversation, conversation_id
    )
    if conversation is None:
        raise ValueError(f"InteractiveQuizConversation {conversation_id} does not exist")
    return conversation
