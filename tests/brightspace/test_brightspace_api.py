from http import HTTPStatus
import os
from ..cheap.test_app import BaseRoutesTestCase

BS_ORG_UNIT_ID = os.environ.get('BS_ORG_UNIT_ID', 360058)
BS_QUIZ_ID = os.environ.get('BS_QUIZ_ID', 102733)
BS_USERNAME = os.environ.get('BS_USERNAME', 's5556775')


class TestBrightspaceAPI(BaseRoutesTestCase):
    
    def test_list_courses(self):
        response = self.client.get('/api/brightspace/list/courses')
        assert response.status_code == HTTPStatus.OK
        assert isinstance(response.json, list)
        # Each course should have the expected keys
        if response.json:
            course = response.json[0]
            assert 'name' in course
            assert 'code' in course
            assert 'bs_org_unit_id' in course

    def test_list_course_quizzes(self):
        response = self.client.get(
            f'/api/brightspace/list/courses/{BS_ORG_UNIT_ID}/quizzes')
        assert response.status_code == HTTPStatus.OK
        assert isinstance(response.json, list)
        # Each quiz should have the expected keys
        if response.json:
            quiz = response.json[0]
            assert 'name' in quiz
            assert 'bs_quiz_id' in quiz

    def test_import_course_quiz(self):
        response = self.client.get(
            f'/api/brightspace/import/courses/{BS_ORG_UNIT_ID}'
            f'/quizzes/{BS_QUIZ_ID}')
        assert response.status_code == HTTPStatus.OK
        assert 'quiz_id' in response.json
        assert isinstance(response.json['quiz_id'], int)

    def test_export_course_quiz(self):
        # First import a quiz so we have a local quiz_id to export back
        import_response = self.client.get(
            f'/api/brightspace/import/courses/{BS_ORG_UNIT_ID}'
            f'/quizzes/{BS_QUIZ_ID}')
        assert import_response.status_code == HTTPStatus.OK
        quiz_id = import_response.json['quiz_id']
        
        response = self.client.post(
            f'/api/brightspace/export/courses/{BS_ORG_UNIT_ID}/quizzes',
            json={'quiz_id': quiz_id})
        assert response.status_code == HTTPStatus.OK

    def test_export_course_quiz_grades(self):
        # First import a quiz so we have a local quiz_id with data
        import_response = self.client.get(
            f'/api/brightspace/import/courses/{BS_ORG_UNIT_ID}'
            f'/quizzes/{BS_QUIZ_ID}')
        assert import_response.status_code == HTTPStatus.OK
        quiz_id = import_response.json['quiz_id']
        
        response = self.client.post(
            f'/api/brightspace/export_grades/courses/{BS_ORG_UNIT_ID}',
            json={
                'quiz_id': quiz_id,
                'grade_name': 'Test Grade',
                'grading_formula': 'ug_bss',
            })
        assert response.status_code == HTTPStatus.OK

    def test_export_course_quiz_missing_quiz_id(self):
        """Export should return 400 when quiz_id is missing."""
        response = self.client.post(
            f'/api/brightspace/export/courses/{BS_ORG_UNIT_ID}/quizzes',
            json={})
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_export_course_quiz_grades_missing_fields(self):
        """Export grades should return 400 when required fields are missing."""
        response = self.client.post(
            f'/api/brightspace/export_grades/courses/{BS_ORG_UNIT_ID}',
            json={})
        assert response.status_code == HTTPStatus.BAD_REQUEST
