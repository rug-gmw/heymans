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
    attempts = relationship('Attempt', back_populates='user')
    documents = relationship('Document', back_populates='user')
    quizzes = relationship('Quiz', back_populates='user')


class Quiz(Model):
    __tablename__ = 'quiz'

    quiz_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.user_id'), nullable=False)
    name = Column(String, nullable=False)

    # Each Quiz has multiple Questions, so we define a one-to-many relationship
    questions = relationship('Question', back_populates='quiz')
    # And is owned by a single user
    user = relationship('User', back_populates='quizzes')
    
    
class Question(Model):
    __tablename__ = 'question'

    question_id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey('quiz.quiz_id'), nullable=False)
    text = Column(Text, nullable=False)
    answer_key = Column(Text)

    # Each Question belongs to a Quiz, and has multiple Answers
    quiz = relationship('Quiz', back_populates='questions')
    attempts = relationship('Attempt', back_populates='question')


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

    # Each Document is associated with one or more document chunks and a user
    chunks = relationship('Chunk', back_populates='document')
    user = relationship('User', back_populates='documents')
    

class Chunk(Model):
    __tablename__ = 'chunk'
    
    chunk_id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('document.document_id'),
                         nullable=False)
    content = Column(Text)

    # Each Document is associated with one or more document chunks and a user
    document = relationship('Document', back_populates='chunks')
