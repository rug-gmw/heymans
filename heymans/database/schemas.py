from .models import Quiz, Question, Attempt, User
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field
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
