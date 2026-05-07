import os
import jsonschema
from heymans import json_schemas

BS_ORG_UNIT_ID = os.environ.get('BS_ORG_UNIT_ID', 360058)
BS_QUIZ_ID = os.environ.get('BS_QUIZ_ID', 102733)


def test_list_courses(brightspace):    
    brightspace.list_courses()
    
def test_list_course_quizzes(brightspace):
    brightspace.list_course_quizzes(BS_ORG_UNIT_ID)

def test_get_quiz(brightspace):
    quiz_info = brightspace.get_quiz(BS_ORG_UNIT_ID, BS_QUIZ_ID)
    jsonschema.validate(quiz_info, json_schemas.QUIZ)
