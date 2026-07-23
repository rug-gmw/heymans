import os
import jsonschema
from heymans import json_schemas
from heymans.brightspace import get_brightspace

BS_ORG_UNIT_ID = os.environ.get('BS_ORG_UNIT_ID', 360058)
BS_QUIZ_ID = os.environ.get('BS_QUIZ_ID', 102733)
BS_USERNAME = os.environ.get('BS_USERNAME', 's5556775')
brightspace = get_brightspace()


def test_list_courses():
    assert isinstance(brightspace.list_courses(), list)
    
def test_list_course_quizzes():
    assert isinstance(brightspace.list_course_quizzes(BS_ORG_UNIT_ID), list)

def test_get_quiz():
    quiz_info = brightspace.get_quiz(BS_ORG_UNIT_ID, BS_QUIZ_ID)
    jsonschema.validate(quiz_info, json_schemas.QUIZ)

def test_post_grades():
    grade_items = [
        {
            "name": "Test grade",
            "description": "Creted by unit test",
            "max_points": 10,
            "grades": [
                {
                    "username": BS_USERNAME,
                    "feedback": "Some feedback",
                    "score": 10
                }
            ]
        }
    ]
    brightspace.post_grades(BS_ORG_UNIT_ID, grade_items)


def test_post_quiz():
    brightspace.post_quiz(BS_ORG_UNIT_ID, 'example/exam-questions.md')
