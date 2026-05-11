import os
import jsonschema
from heymans import json_schemas

BS_ORG_UNIT_ID = os.environ.get('BS_ORG_UNIT_ID', 360058)
BS_QUIZ_ID = os.environ.get('BS_QUIZ_ID', 102733)
BS_USERNAME = os.environ.get('BS_USERNAME', 's5556775')


def test_list_courses(brightspace):    
    brightspace.list_courses()
    
def test_list_course_quizzes(brightspace):
    brightspace.list_course_quizzes(BS_ORG_UNIT_ID)

def test_get_quiz(brightspace):
    quiz_info = brightspace.get_quiz(BS_ORG_UNIT_ID, BS_QUIZ_ID)
    jsonschema.validate(quiz_info, json_schemas.QUIZ)

def test_post_grades(brightspace):
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
