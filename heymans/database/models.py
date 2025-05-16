import logging
import os
logger = logging.getLogger('heymans')
# Depending on whether we are running inside a Flask app or not, we need to
# instantiate the database model differently. It is difficult to determine
# automatically whether Flask is running, because at this point we're still
# in the initialization phase. Therefore, we're explicitly setting an 
# environment variable when creating the Flask app.
from sqlalchemy.orm.exc import NoResultFound
if os.environ.get('USE_FLASK_SQLALCHEMY', False):
    logger.info('using flask_sqlachemy')
    from flask_sqlalchemy import SQLAlchemy as _BaseSQLAlchemy
    db = _BaseSQLAlchemy()
    Column = db.Column
    Integer = db.Integer
    Boolean = db.Boolean
    String = db.String
    Text = db.Text
    ForeignKey = db.ForeignKey
    LargeBinary = db.LargeBinary
    DateTime = db.DateTime
    Model = db.Model
    relationship = db.relationship
    # NoResultFound = db.NoResultFound
else:
    from sqlalchemy import create_engine, Column, Integer, String, \
        ForeignKey, LargeBinary, DateTime, Text, Boolean
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import scoped_session, sessionmaker, relationship
    import logging
    logger.info('using standalone_sqlachemy')
    engine = create_engine('sqlite:///:memory:')
    session = scoped_session(sessionmaker(autocommit=False, autoflush=False,
                                          bind=engine))
    Base = declarative_base()
    # Create a db object that mimics Flask-SQLAlchemy's, with Model as an 
    # attribute
    class SQLAlchemy:
        def __init__(self, metadata):
            self.Model = declarative_base(metadata=metadata)
    db = SQLAlchemy(metadata=Base.metadata)
    db.session = session
    Model = db.Model
    Model.query = session.query_property()
    def init_db(): Model.metadata.create_all(bind=engine)
    def drop_db(): Model.metadata.drop_all(bind=engine)
    
    
class User(Model):
    __tablename__ = 'user'

    user_id = Column(Integer, primary_key=True)
    username = Column(String(80))

    # Each User has multiple Attempts, so we define a one-to-many relationship
    attempts = relationship('Attempt', back_populates='user',
                            cascade='all, delete-orphan')
    documents = relationship('Document', back_populates='user',
                             cascade='all, delete-orphan')
    quizzes = relationship('Quiz', back_populates='user',
                           cascade='all, delete-orphan')
    interactive_quizzes = relationship(
        'InteractiveQuiz',
        back_populates='user',
        cascade='all, delete-orphan')
    interactive_quiz_conversations = relationship(
        'InteractiveQuizConversation',
        back_populates='user',
        cascade='all, delete-orphan')
    


class Quiz(Model):
    __tablename__ = 'quiz'

    quiz_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.user_id'), nullable=False)
    name = Column(String, nullable=False)
    validation = Column(Text, nullable=True)

    # Each Quiz has multiple Questions, so we define a one-to-many relationship
    questions = relationship('Question', back_populates='quiz',
                             cascade='all, delete-orphan')
    # And is owned by a single user
    user = relationship('User', back_populates='quizzes')
    
    
class Question(Model):
    __tablename__ = 'question'

    question_id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey('quiz.quiz_id'), nullable=False)
    name = Column(String, nullable=True)
    text = Column(Text, nullable=False)
    answer_key = Column(Text)

    # Each Question belongs to a Quiz, and has multiple Answers
    quiz = relationship('Quiz', back_populates='questions')
    attempts = relationship('Attempt', back_populates='question',
                            cascade='all, delete-orphan')


class Attempt(Model):
    __tablename__ = 'attempt'

    attempt_id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey('question.question_id'),
                         nullable=False)
    user_id = Column(Integer, ForeignKey('user.user_id'), nullable=False)
    answer = Column(Text, nullable=False)
    feedback = Column(Text)
    score = Column(Integer)

    # Each Answer is associated with a Question and a user
    question = relationship('Question', back_populates='attempts')
    user = relationship('User', back_populates='attempts')


class Document(Model):
    __tablename__ = 'document'
    
    document_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.user_id'), nullable=False)
    public = Column(Boolean, nullable=False)

    # Each Document is associated with one or more document chunks, interactive quizzes, and a user
    chunks = relationship('Chunk', back_populates='document',
                          cascade='all, delete-orphan')
    user = relationship('User', back_populates='documents')
    interactive_quizzes = relationship('InteractiveQuiz',
                                       back_populates='document',
                                       cascade='all, delete-orphan')
    

class Chunk(Model):
    __tablename__ = 'chunk'
    
    chunk_id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('document.document_id'),
                         nullable=False)
    content = Column(Text)

    # Each Document is associated with one or more document chunks and a user
    document = relationship('Document', back_populates='chunks')


class InteractiveQuiz(Model):
    """A shareable quiz based on a single document, owned by a user."""

    __tablename__ = 'interactive_quiz'

    interactive_quiz_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.user_id'), nullable=False)
    document_id = Column(Integer, ForeignKey('document.document_id'),
                         nullable=False)

    # Properties
    name = Column(String, nullable=False)
    public = Column(Boolean, nullable=False, default=False)

    # Relationships
    user = relationship('User', back_populates='interactive_quizzes')
    document = relationship('Document', back_populates='interactive_quizzes')
    conversations = relationship('InteractiveQuizConversation',
                                 back_populates='interactive_quiz',
                                 cascade='all, delete-orphan')


class InteractiveQuizConversation(Model):
    """A (possibly multi-turn) chat session between a student and Heymans."""

    __tablename__ = 'interactive_quiz_conversation'

    conversation_id = Column(Integer, primary_key=True)
    interactive_quiz_id = Column(Integer,
                                 ForeignKey('interactive_quiz.interactive_quiz_id'),
                                 nullable=False)
    user_id = Column(Integer, ForeignKey('user.user_id'), nullable=False)

    # Properties
    finished = Column(Boolean, nullable=False, default=False)

    # Relationships
    interactive_quiz = relationship('InteractiveQuiz',
                                    back_populates='conversations')
    user = relationship('User', back_populates='interactive_quiz_conversations')
    messages = relationship('InteractiveQuizMessage',
                            back_populates='conversation',
                            cascade='all, delete-orphan')


class InteractiveQuizMessage(Model):
    """An individual message (question, answer, system prompt, etc.)
    in an InteractiveQuizConversation.
    """

    __tablename__ = 'interactive_quiz_message'

    message_id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer,
                             ForeignKey('interactive_quiz_conversation.conversation_id'),
                             nullable=False)

    # Properties
    text = Column(Text, nullable=False)
    message_type = Column(String, nullable=False)  # e.g. 'question', 'answer'

    # Relationships
    conversation = relationship('InteractiveQuizConversation',
                                back_populates='messages')