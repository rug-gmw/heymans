import logging
from typing import List, Dict, Any, Optional
from ..models import db, QAConversation, QAMessage, Document
from ..schemas import QAConversationSchema, QAMessageSchema

logger = logging.getLogger("heymans")

# Re-use schema instances for efficiency
qa_conversation_schema = QAConversationSchema()
qa_message_schema = QAMessageSchema()


def new_qa_conversation(name: str, user_id: int) -> int:
    """Adds a new Q&A conversation to the database and returns its ID."""
    with db.session.begin():
        conversation = QAConversation(
            name=name,
            user_id=user_id,
        )
        db.session.add(conversation)
        db.session.flush()
        logger.info(
            "Created Q&A conversation %s for user %s",
            conversation.qa_conversation_id,
            user_id,
        )
        return conversation.qa_conversation_id


def list_qa_conversations(user_id: int) -> List[Dict[str, Any]]:
    """
    Returns all Q&A conversations owned by the given user.

    Returned structure:
        [{"name": <str>, "qa_conversation_id": <int>}, ...]
    """
    with db.session.begin():
        conversations = (
            db.session.query(QAConversation)
            .filter(QAConversation.user_id == user_id)
            .all()
        )
        logger.debug("User %s has %d Q&A conversations", user_id, len(conversations))
        return [
            {
                "name": conv.name,
                "qa_conversation_id": conv.qa_conversation_id
            }
            for conv in conversations
        ]


def get_qa_conversation(qa_conversation_id: int, user_id: int) -> Dict[str, Any]:
    """
    Returns a serialised representation of the Q&A conversation with all messages.

    Raises
    ------
    NoResultFound
        If the conversation does not exist or user doesn't have access.
    """
    with db.session.begin():
        conversation = _get_conversation(qa_conversation_id, user_id)
        
        # Use schema to serialize the conversation
        schema = QAConversationSchema()
        result = schema.dump(conversation)
        
        logger.debug("Loaded Q&A conversation %s for user %s", qa_conversation_id, user_id)
        return result        


def delete_qa_conversation(qa_conversation_id: int, user_id: int) -> None:
    """
    Deletes a Q&A conversation owned by the current user.

    Raises
    ------
    Exception
        If the conversation does not exist or user doesn't own it.
    """
    with db.session.begin():
        conversation = _get_conversation(qa_conversation_id, user_id)
        # Messages and sources will be cascade deleted
        db.session.delete(conversation)
        logger.info("Deleted Q&A conversation %s by user %s", qa_conversation_id, user_id)


def new_qa_message(qa_conversation_id: int, user_id: int, text: str, role: str,
                   document_ids: Optional[List[int]] = None) -> int:
    """
    Adds a new Q&A message to the database and returns its ID.
    
    Parameters
    ----------
    qa_conversation_id : int
        The conversation ID
    user_id : int
        The user ID (for permission check)
    text : str
        The message text
    role : str
        Either "user" or "ai"
    document_ids : List[int], optional
        List of document IDs that serve as sources for the message
    """
    with db.session.begin():
        _get_conversation(qa_conversation_id, user_id)  # Check access
        
        message = QAMessage(
            qa_conversation_id=qa_conversation_id,  # Fixed: should be qa_conversation_id
            text=text,
            role=role
        )
        
        # Link documents if provided
        if document_ids:
            documents = db.session.query(Document).filter(
                Document.document_id.in_(document_ids)
            ).all()
            message.documents = documents
            
        db.session.add(message)
        db.session.flush()        
        logger.info(f"New Q&A message {message.qa_message_id} (role={role}, {len(document_ids or [])} documents)")
        return message.qa_message_id


## Helpers


def _get_conversation(qa_conversation_id: int, user_id: int) -> QAConversation:
    """
    Helper that returns a Q&A conversation if the user owns it, or raises an 
    Exception otherwise.
    """
    conversation: QAConversation | None = db.session.get(QAConversation, qa_conversation_id)
    if conversation is None:
        from ..models import NoResultFound
        raise NoResultFound(f"Q&A conversation {qa_conversation_id} does not exist")
    if conversation.user_id != user_id:
        raise PermissionError("You do not have permission to access this conversation")
    return conversation
