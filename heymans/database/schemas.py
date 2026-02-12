from .models import (Quiz, Question, Attempt, Document, Chunk, InteractiveQuiz,
                     InteractiveQuizConversation, InteractiveQuizMessage)
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from marshmallow import fields


class AttemptSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Attempt
        load_instance = True
    username = fields.Method("get_username")

    def get_username(self, attempt):
        return attempt.username


class QuestionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Question
        load_instance = True
    attempts = fields.Nested(AttemptSchema, many=True)
    

class QuizSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Quiz
        load_instance = True
    questions = fields.Nested(QuestionSchema, many=True)
    
    
class ChunkSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Chunk
        load_instance = True
    
    
class DocumentSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Document
        load_instance = True
    

class DocumentWithChunksSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Document
        load_instance = True
    chunks = fields.Nested(ChunkSchema, many=True)


class InteractiveQuizMessageSchema(SQLAlchemyAutoSchema):
    """Schema for a single message within an interactive-quiz conversation."""
    class Meta:
        model = InteractiveQuizMessage
        load_instance = True


class InteractiveQuizConversationSchema(SQLAlchemyAutoSchema):
    """Schema for one conversation (chat session) in an interactive quiz."""
    class Meta:
        model = InteractiveQuizConversation
        load_instance = True

    # Nested messages
    messages = fields.Nested(InteractiveQuizMessageSchema, many=True)

    # Convenience: expose the participant’s username
    username = fields.Method("get_username")
    user_id = fields.Method("get_user_id")
    
    # Expose the associated document chunks
    chunks = fields.Method("get_chunks")

    def get_username(self, conversation):
        return conversation.user.username
        
    def get_user_id(self, conversation):
        return conversation.user_id

    def get_chunks(self, conversation):
        # Access chunks via the chain: conversation -> interactive_quiz -> document -> chunks
        document = conversation.interactive_quiz.document
        return ChunkSchema(many=True).dump(document.chunks) if document else []


class InteractiveQuizSchema(SQLAlchemyAutoSchema):
    """Top-level schema representing a shareable interactive quiz."""
    class Meta:
        model = InteractiveQuiz
        load_instance = True

    # All conversations belonging to the quiz
    conversations = fields.Nested(InteractiveQuizConversationSchema, many=True)

    # Convenience fields
    username = fields.Method("get_username")          # quiz owner
    user_id = fields.Method("get_user_id")

    def get_username(self, interactive_quiz):
        return interactive_quiz.user.username# 
        
    def get_user_id(self, interactive_quiz):
        return interactive_quiz.user_id
