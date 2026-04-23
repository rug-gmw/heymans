import secrets
from sqlalchemy.exc import IntegrityError
import logging
from typing import List, Dict, Any
import random
from ..models import db, InteractiveQuiz, InteractiveQuizConversation, \
    InteractiveQuizMessage
from ..schemas import InteractiveQuizSchema, InteractiveQuizConversationSchema
from ... import prompts, chatbot_model

logger = logging.getLogger("heymans")

# JavaScript uses a different maximum integer. We avoid generating IDs beyond
# the safe range to avoid issues in communicating the ID back and forth.
MAX_SAFE_JS_INT = 2 ** 53 - 1

# Re-use one schema instance for efficiency
interactive_quiz_schema = InteractiveQuizSchema()
interactive_quiz_conversation_schema = InteractiveQuizConversationSchema()

def new_interactive_quiz(name: str, document_id: int, user_id: int,
                         public: bool = False) -> int:
    """Adds a new interactive quiz to the database and returns its ID."""
    # An infinite loop in case we accidentally draw a duplicate ID. This is
    # extremely unlikely, but just in case.
    while True:
        try:
            with db.session.begin():
                quiz = InteractiveQuiz(
                    interactive_quiz_id=secrets.randbelow(MAX_SAFE_JS_INT + 1),
                    name=name,
                    document_id=document_id,
                    user_id=user_id,
                    public=public,
                )
                db.session.add(quiz)
                db.session.flush()
                logger.info(
                    "Created interactive quiz %s (document=%s, public=%s) for user %s",
                    quiz.interactive_quiz_id,
                    document_id,
                    public,
                    user_id,
                )
                return quiz.interactive_quiz_id
        except IntegrityError:
            logger.warning("Interactive quiz ID collision on attempt, retrying")
            continue
        break

        
def rename_interactive_quiz(interactive_quiz_id: int, user_id: int,
                            new_name: str):
    """Renames a quiz owned by the current user."""
    with db.session.begin():
        quiz = _get_quiz(interactive_quiz_id, user_id)
        if quiz.user_id != user_id:
            raise PermissionError("Only the owner can rename this quiz")
        quiz.name = new_name
        logger.info("Renamed interactive quiz %s to %s", interactive_quiz_id, new_name)


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
                                      username: str,
                                      model: str) -> (int, str):
    """Adds a new interactive quiz conversation to the database and returns
    its ID and the question. A conversation can be started by any user.
    """
    with db.session.begin():
        quiz = _get_quiz(interactive_quiz_id)  # Check if quiz exists
        chunk_id = random.choice(quiz.document.chunks).chunk_id
        logger.info(f'Starting conversation with chunk {chunk_id}')
        conversation = InteractiveQuizConversation(
            interactive_quiz_id=interactive_quiz_id,
            chunk_id=chunk_id,
            username=username)
        db.session.add(conversation)        
        db.session.flush()
        conversation_id = conversation.conversation_id
    # Get a question
    conversation = get_interactive_quiz_conversation(conversation_id)
    questions = chatbot_model.static_predict(
        prompts.INTERACTIVE_QUIZ_QUESTION_PROMPT.render(
            source=conversation['chunk']['content']),
        model=model, json=True,
        dummy_reply=[{"question": "dummy", "skill": "dummy"}])
    question = random.choice(questions)
    # Start the conversation
    new_interactive_quiz_message(conversation_id, "Ask me anything!", 'user')
    new_interactive_quiz_message(conversation_id, question['question'], 'ai')
    logger.info(f"New InteractiveQuizConversation {conversation_id}")
    return conversation_id, question['question']


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


def finished(interactive_quiz_id: int, username: str) -> int:
    """Returns the number of finished conversations for a username and quiz."""
    with db.session.begin():
        count = (
            db.session.query(InteractiveQuizConversation)
            .filter(
                InteractiveQuizConversation.interactive_quiz_id == interactive_quiz_id,
                InteractiveQuizConversation.username == username,
                InteractiveQuizConversation.finished.is_(True)
            )
            .count()
        )
        logger.debug("User %s has %d finished conversation(s) for quiz %s",
                     username, count, interactive_quiz_id)
        return count


def get_interactive_quiz_logs(interactive_quiz_id: int,
                              owner_user_id: str | int,
                              student_username: str) -> Dict[str, Any]:
    """Return all logged conversations/messages for one student in one quiz.

    Semantics:
      - owner_user_id: the (authenticated) quiz owner
      - student_username: the student identifier saved on conversations
    """
    student_username = (student_username or "").strip()
    if not student_username:
        raise ValueError("student_username is required")

    with db.session.begin():
        quiz = _get_quiz(interactive_quiz_id, owner_user_id)
        conversation_ids = [
            row[0]
            for row in (
                db.session.query(InteractiveQuizConversation.conversation_id)
                .filter(
                    InteractiveQuizConversation.interactive_quiz_id == interactive_quiz_id,
                    InteractiveQuizConversation.username == student_username,
                )
                .order_by(InteractiveQuizConversation.conversation_id.asc())
                .all()
            )
        ]
        quiz_name = quiz.name

    conversations: List[Dict[str, Any]] = []
    for conversation_id in conversation_ids:
        conversation = get_interactive_quiz_conversation(conversation_id)
        messages = sorted(
            conversation.get("messages", []),
            key=lambda message: message["message_id"],
        )
        normalized_messages = [
            {
                "message_id": message["message_id"],
                "role": _map_message_type_to_role(message["message_type"]),
                "text": message["text"],
            }
            for message in messages
        ]
        conversations.append({
            "conversation_id": conversation["conversation_id"],
            "finished": conversation["finished"],
            "messages": _strip_hidden_initial_user_message(normalized_messages),
        })

    finished_count = sum(1 for conversation in conversations if conversation["finished"])
    return {
        "interactive_quiz_id": interactive_quiz_id,
        "quiz_name": quiz_name,
        "owner_user_id": owner_user_id,
        "student_username": student_username,
        "started_count": len(conversations),
        "finished_count": finished_count,
        "conversations": conversations,
    }


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


def _map_message_type_to_role(message_type: str) -> str:
    """Map DB message type values to frontend role values."""
    return "assistant" if message_type == "ai" else "user"


def _strip_hidden_initial_user_message(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Match session UI behavior by hiding the synthetic opening user message."""
    if not messages:
        return messages
    first_message = messages[0]
    if (
        first_message.get("role") == "user"
        and (first_message.get("text") or "").strip() == "Ask me anything!"
    ):
        return messages[1:]
    return messages
