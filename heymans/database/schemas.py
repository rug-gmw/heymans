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
        return attempt.user.username


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

    def get_username(self, conversation):
        return conversation.user.username


class InteractiveQuizSchema(SQLAlchemyAutoSchema):
    """Top-level schema representing a shareable interactive quiz."""
    class Meta:
        model = InteractiveQuiz
        load_instance = True

    # All conversations belonging to the quiz
    conversations = fields.Nested(InteractiveQuizConversationSchema, many=True)

    # Convenience fields
    username = fields.Method("get_username")          # quiz owner
    # document_name = fields.Method("get_document_name")

    def get_username(self, interactive_quiz):
        return interactive_quiz.user.username

    # def get_document_name(self, interactive_quiz):
        # return interactive_quiz.document.name
# 