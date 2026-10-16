import secrets
from sqlalchemy.exc import IntegrityError
import logging
from typing import List, Dict, Any
import random
import json
from datetime import datetime, timezone
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
DEFAULT_ENABLED_SKILLS = ["understand", "apply", "analyze", "evaluate", "create"]


def new_interactive_quiz(name: str, document_id: int, user_id: int,
                         public: bool = False,
                         enabled_skills: list[str] | None = None,
                         start_date: str | None = None,
                         end_date: str | None = None) -> int:
    """Adds a new interactive quiz to the database and returns its ID.

    start_date and end_date are ISO 8601 datetime strings that determine
    when conversations with the quiz can be started. They are stored as
    naive UTC datetimes; None (the default) means no restriction.
    """
    enabled_skills = enabled_skills or DEFAULT_ENABLED_SKILLS.copy()
    start_date = _parse_datetime(start_date, 'start_date')
    end_date = _parse_datetime(end_date, 'end_date')
    _assert_valid_date_range(start_date, end_date)

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
                    enabled_skills=json.dumps(enabled_skills),
                    start_date=start_date,
                    end_date=end_date,
                )
                db.session.add(quiz)
                db.session.flush()
                logger.info(
                    "Created interactive quiz %s (document=%s, public=%s, enabled_skills=%s) for user %s",
                    quiz.interactive_quiz_id,
                    document_id,
                    public,
                    enabled_skills,
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


def update_interactive_quiz_settings(
    interactive_quiz_id: int,
    user_id: int,
    enabled_skills: list[str],
    document_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Update quiz settings for a quiz owned by the current user.

    start_date and end_date are ISO 8601 datetime strings that determine when
    conversations with the quiz can be started; None means no restriction, so
    passing None clears the corresponding date. The caller is responsible for
    merging these values with the current ones when a setting should be left
    unchanged. Changing the dates does not clear existing conversations.
    """
    start_date = _parse_datetime(start_date, 'start_date')
    end_date = _parse_datetime(end_date, 'end_date')
    _assert_valid_date_range(start_date, end_date)
    with db.session.begin():
        quiz = _get_quiz(interactive_quiz_id, user_id)
        if quiz.user_id != user_id:
            raise PermissionError("Only the owner can update this quiz")
        previous_enabled_skills = _get_quiz_enabled_skills(quiz)
        previous_document_id = quiz.document_id

        quiz.enabled_skills = json.dumps(enabled_skills)
        quiz.document_id = document_id
        quiz.start_date = start_date
        quiz.end_date = end_date

        if previous_enabled_skills != enabled_skills or previous_document_id != document_id:
            _clear_quiz_conversations(interactive_quiz_id)
        logger.info(
            "Updated settings for interactive quiz %s: document_id=%s, enabled_skills=%s, start_date=%s, end_date=%s",
            interactive_quiz_id,
            document_id,
            enabled_skills,
            start_date,
            end_date,
        )
    return {
        "enabled_skills": enabled_skills,
        "document_id": document_id,
        "start_date": _serialize_datetime(start_date),
        "end_date": _serialize_datetime(end_date),
    }


def list_interactive_quizzes(user_id: int) -> List[Dict[str, Any]]:
    """
    Returns all interactive quizzes visible to the given user.

    A quiz is visible when:
      • the user owns it, OR
      • it is marked public.

    Returned structure:
        [
            {
                "name": <str>,
                "quiz_id": <int>,
                "start_date": <str or None>,
                "end_date": <str or None>,
                "is_open": <bool>,
            },
            ...
        ]

    Quizzes are included regardless of their dates; the dates are reported as
    ISO 8601 strings (naive UTC), and is_open indicates whether the quiz can
    currently be started.
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
        return [
            {
                "name": quiz.name,
                "quiz_id": quiz.interactive_quiz_id,
                "start_date": _serialize_datetime(quiz.start_date),
                "end_date": _serialize_datetime(quiz.end_date),
                "is_open": _quiz_is_open(quiz),
            }
            for quiz in quizzes
        ]


def list_owned_interactive_quizzes_for_export(user_id: int) -> List[Dict[str, Any]]:
    """
    Returns a lightweight representation of all interactive quizzes that are
    owned by the given user (public quizzes owned by others are not included).

    Unlike get_interactive_quiz(), this doesn't serialise chunks or messages,
    because the export only needs to know who has started and finished what.

    Returned structure:
        [
            {
                "interactive_quiz_id": <int>,
                "name": <str>,
                "conversations": [
                    {"username": <str>, "finished": <bool>}, ...
                ]
            },
            ...
        ]
    """
    with db.session.begin():
        quizzes = (
            db.session.query(InteractiveQuiz)
            .filter(InteractiveQuiz.user_id == user_id)
            .order_by(InteractiveQuiz.name, InteractiveQuiz.interactive_quiz_id)
            .all()
        )
        logger.debug("User %s owns %d interactive quizzes", user_id,
                     len(quizzes))
        return [
            {
                "interactive_quiz_id": quiz.interactive_quiz_id,
                "name": quiz.name,
                "conversations": [
                    {"username": conversation.username,
                     "finished": conversation.finished}
                    for conversation in quiz.conversations
                ],
            }
            for quiz in quizzes
        ]


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
    its ID and the question. A conversation can be started by any user, but
    only while the quiz is within its start_date / end_date window.
    """
    # start conversation in db:
    with db.session.begin():
        quiz = _get_quiz(interactive_quiz_id)  # Check if quiz exists
        _assert_quiz_is_open(quiz)
        enabled_skills = _get_quiz_enabled_skills(quiz)
        chunk_id = random.choice(quiz.document.chunks).chunk_id
        logger.info(f'Starting conversation with chunk {chunk_id}')
        conversation = InteractiveQuizConversation(
            interactive_quiz_id=interactive_quiz_id,
            chunk_id=chunk_id,
            username=username,
            bloom_skill="")
        db.session.add(conversation)        
        db.session.flush()
        conversation_id = conversation.conversation_id
    
    logger.info(f"New InteractiveQuizConversation {conversation_id}")
    conversation = get_interactive_quiz_conversation(conversation_id)
    
    # Generate questions:
    questions = chatbot_model.static_predict(
        prompts.INTERACTIVE_QUIZ_QUESTION_PROMPT.render(
            source=conversation['chunk']['content'],
            enabled_skills=", ".join(enabled_skills)),
        model=model, json=True,
        dummy_reply=[{"question": "dummy", "skill": enabled_skills[0]}])
    if not isinstance(questions, list) or not questions:
        raise ValueError("Chatbot didn't generate valid question(s)")
    question = random.choice(questions)
    question_text = question['question']
    question_skill = question['skill']
    # attach the skill to the conversation in the db:
    with db.session.begin():
        conversation = _get_conversation(conversation_id)
        conversation.bloom_skill = question_skill
    # Start the conversation:
    new_interactive_quiz_message(conversation_id, "Ask me anything!", 'user')
    new_interactive_quiz_message(conversation_id, question_text, 'ai')
    return conversation_id, question_text


def assert_conversation_quiz_is_open(conversation_id: int) -> None:
    """Raise ValueError if the quiz that a conversation belongs to is not
    currently open (i.e. outside of its start_date / end_date window).

    This is used to cut off in-flight conversations once a quiz closes.
    """
    with db.session.begin():
        conversation = _get_conversation(conversation_id)
        _assert_quiz_is_open(conversation.interactive_quiz)


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
                "message_type": message["message_type"],
                "text": message["text"],
            }
            for message in messages
        ]
        conversations.append({
            "conversation_id": conversation["conversation_id"],
            "finished": conversation["finished"],
            "bloom_skill": conversation.get("bloom_skill"),
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


def _strip_hidden_initial_user_message(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Match session UI behavior by hiding the synthetic opening user message."""
    if not messages:
        return messages
    first_message = messages[0]
    if (
        first_message.get("message_type") == "user"
        and (first_message.get("text") or "").strip() == "Ask me anything!"
    ):
        return messages[1:]
    return messages


def _clear_quiz_conversations(interactive_quiz_id: int) -> None:
    """Delete all conversations for a quiz (cascades to messages)."""
    db.session.query(InteractiveQuizConversation).filter(
        InteractiveQuizConversation.interactive_quiz_id == interactive_quiz_id
    ).delete(synchronize_session=False)

def _get_quiz_enabled_skills(quiz: InteractiveQuiz) -> list[str]:
    """Return enabled skills from the quiz model."""
    return json.loads(quiz.enabled_skills)


def _parse_datetime(value: str | None,
                    field_name: str = 'date') -> datetime | None:
    """Parse an ISO 8601 datetime string into a naive UTC datetime.

    None and empty strings are returned as None, meaning 'no restriction'.
    A value with a timezone offset is converted to UTC; a value without an
    offset is assumed to already be in UTC. A date-only value (e.g.
    '2030-01-01') is interpreted as midnight of that day. Raises ValueError
    with a friendly message if the value is not a valid datetime.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if not isinstance(value, str):
        raise ValueError(
            f"Invalid {field_name}: {value!r} (expected an ISO 8601 "
            f"datetime, such as '2030-01-01T12:00:00')")
    text = value.strip()
    # Python (before 3.11) cannot parse the 'Z' suffix that denotes UTC
    if text.endswith(('Z', 'z')):
        text = text[:-1] + '+00:00'
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(
            f"Invalid {field_name}: {value!r} (expected an ISO 8601 "
            f"datetime, such as '2030-01-01T12:00:00')")
    if parsed.tzinfo is not None:
        # Normalize to naive UTC, the storage convention for all dates
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _serialize_datetime(value: datetime | None) -> str | None:
    """Serialize a naive UTC datetime as an ISO 8601 string."""
    return value.isoformat() if value is not None else None


def _assert_valid_date_range(start_date: datetime | None,
                             end_date: datetime | None) -> None:
    """Raise ValueError if end_date is before start_date."""
    if start_date is not None and end_date is not None \
            and end_date < start_date:
        raise ValueError("end_date cannot be before start_date")


def _utcnow() -> datetime:
    """The current time as a naive UTC datetime (the storage convention)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _quiz_is_open(quiz: InteractiveQuiz) -> bool:
    """Return True if the quiz is within its start_date / end_date window.

    A quiz without dates is always open. The quiz is open from start_date
    (inclusive) until end_date (exclusive).
    """
    now = _utcnow()
    if quiz.start_date is not None and now < quiz.start_date:
        return False
    if quiz.end_date is not None and now >= quiz.end_date:
        return False
    return True


def _assert_quiz_is_open(quiz: InteractiveQuiz) -> None:
    """Raise ValueError with an informative message if the quiz is outside
    of its start_date / end_date window."""
    now = _utcnow()
    if quiz.start_date is not None and now < quiz.start_date:
        raise ValueError(
            "This chat quiz has not opened yet (it opens at "
            f"{_serialize_datetime(quiz.start_date)} UTC)")
    if quiz.end_date is not None and now >= quiz.end_date:
        raise ValueError(
            "This chat quiz has closed (the deadline was "
            f"{_serialize_datetime(quiz.end_date)} UTC)")
