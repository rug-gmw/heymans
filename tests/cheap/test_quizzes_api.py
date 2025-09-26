import time
import tempfile
import zipfile
from http import HTTPStatus
from .test_app import BaseRoutesTestCase
import jsonschema
from heymans import json_schemas


DUMMY_QUIZ_DATA = '''# Cute bunny awareness exam

## Cutest bunny

Who is the cutest bunny?

- Must state that the cutest bunny is Boef
'''
DUMMY_ATTEMPTS = '''Answer,Q Title,Username
"The cutest bunny is Boef","Cutest bunny","s00000001"
"I do not know :-(","Cutest bunny","s00000002"
'''


class TestQuizzesGradingAPI(BaseRoutesTestCase):
        
    def test_basics(self):
        # Listing should be empty
        response = self.client.get('/api/quizzes/list')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json) == 0
        # Create a new quiz
        response = self.client.post('/api/quizzes/new', json={'name': 'Test'})
        assert response.status_code == HTTPStatus.OK
        assert response.json['quiz_id'] == 1
        # Check if the new quiz matches the dummy data that is was created with
        response = self.client.get('/api/quizzes/get/1')
        assert response.status_code == HTTPStatus.OK
        # Listing should now have one quiz
        response = self.client.get('/api/quizzes/list')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json) == 1
        # Create a second quiz with the same new, and ensure the name has a
        # unique suffix
        response = self.client.post('/api/quizzes/new', json={'name': 'Test'})
        assert response.status_code == HTTPStatus.OK
        assert response.json['quiz_id'] == 2
        response = self.client.get('/api/quizzes/get/2')
        assert response.status_code == HTTPStatus.OK
        assert response.json['name'] == 'Test (1)'
        
    def test_grading(self):
    
        # Create a new quiz
        response = self.client.post('/api/quizzes/new', json={'name': 'Test'})
        assert response.status_code == HTTPStatus.OK
        assert response.json['quiz_id'] == 1
        # Check that state is empty
        response = self.client.get('/api/quizzes/state/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json['state'] == 'empty'
        # Add questions to quiz
        response = self.client.post('/api/quizzes/add/questions/1',
                                    json={'questions': DUMMY_QUIZ_DATA})
        assert response.status_code == HTTPStatus.OK
        # Check that state is has_questions
        response = self.client.get('/api/quizzes/state/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json['state'] == 'has_questions'
        # Add attempts to quiz
        response = self.client.post('/api/quizzes/add/attempts/1',
                                    json={'attempts': DUMMY_ATTEMPTS})
        assert response.status_code == HTTPStatus.OK
        # Check that state is has_attempts
        response = self.client.get('/api/quizzes/state/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json['state'] == 'has_attempts'
        # Check that the quiz needs grading
        response = self.client.get('/api/quizzes/grading/poll/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json['state'] == 'needs_grading'
        # Start grading
        response = self.client.post('/api/quizzes/grading/start/1',
                                    json={'model': 'dummy'})
        assert response.status_code == HTTPStatus.OK
        # Grading should now be in progress
        response = self.client.get('/api/quizzes/grading/poll/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json['state'] == 'grading_in_progress'
        time.sleep(1)
        # Grading should now be done
        response = self.client.get('/api/quizzes/grading/poll/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json['state'] == 'grading_done'
        response = self.client.get('/api/quizzes/get/1')
        assert response.status_code == HTTPStatus.OK
        for attempt in response.json['questions'][0]['attempts']:
            assert attempt['score'] == 1
            assert attempt['feedback'][0]['motivation'] == 'Dummy model'
        jsonschema.validate(response.json, json_schemas.QUIZ)
        # Check that state is has_scores
        response = self.client.get('/api/quizzes/state/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json['state'] == 'has_scores'
        # Export grades
        response = self.client.post('/api/quizzes/export/grades/1')
        assert response.status_code == HTTPStatus.OK
        # Export grades
        response = self.client.get(
            '/api/quizzes/export/difficulty_and_discrimination/1')
        assert response.status_code == HTTPStatus.OK
        assert 'content' in response.json
        # Export individual feedback
        response = self.client.post('/api/quizzes/export/feedback/1')
        assert response.content_type == 'application/zip'
        # Write response.data to a temporary file and ensure it's a zip file
        with tempfile.NamedTemporaryFile() as f:
            f.write(response.data)
            f.flush()
            assert zipfile.is_zipfile(f.name)

    def test_validation(self):
        
        # Create a new quiz
        response = self.client.post('/api/quizzes/new', json={'name': 'Test'})
        assert response.status_code == HTTPStatus.OK
        assert response.json['quiz_id'] == 1
        # Add questions to quiz
        response = self.client.post('/api/quizzes/add/questions/1',
                                    json={"questions": DUMMY_QUIZ_DATA})
        assert response.status_code == HTTPStatus.OK        
        # Check that the quiz needs validation
        response = self.client.get('/api/quizzes/validation/poll/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json['state'] == 'needs_validation'
        # Start validation
        response = self.client.post('/api/quizzes/validation/start/1',
                                    json={'model': 'dummy'})
        assert response.status_code == HTTPStatus.OK
        # Validation should now be in progress
        response = self.client.get('/api/quizzes/validation/poll/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json['state'] == 'validation_in_progress'
        time.sleep(1)
        # Validation should now be done
        response = self.client.get('/api/quizzes/validation/poll/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json['state'] == 'validation_done'
        response = self.client.get('/api/quizzes/get/1')
        assert response.status_code == HTTPStatus.OK
        assert 'Awesome question' in response.json['validation']
        jsonschema.validate(response.json, json_schemas.QUIZ)
        
    def test_export(self):
        # Create a new quiz
        response = self.client.post('/api/quizzes/new', json={'name': 'Test'})
        assert response.status_code == HTTPStatus.OK
        assert response.json['quiz_id'] == 1
        # Check that the export is empty because we haven't uploaded the
        # questions yet
        response = self.client.get('/api/quizzes/export/brightspace/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json['content'] == ''
        # Add questions to quiz
        response = self.client.post('/api/quizzes/add/questions/1',
                                    json={"questions": DUMMY_QUIZ_DATA})
        assert response.status_code == HTTPStatus.OK        
        # Check that we now have a valid export, using the number of lines as an
        # indicator
        response = self.client.get('/api/quizzes/export/brightspace/1')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json['content'].splitlines()) == 7
