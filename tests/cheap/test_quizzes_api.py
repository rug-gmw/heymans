import time
from http import HTTPStatus
from .test_app import BaseRoutesTestCase
import jsonschema
from heymans import json_schemas, config
from sigmund.model import _dummy_model


DUMMY_QUIZ_DATA = '''# Cute bunny awareness exam

## Cutest bunny

Who is the cutest bunny?

- Must state that the cutest bunny is Boef
'''
DUMMY_ATTEMPTS = '''Answer,Q Title,Username
"The cutest bunny is Boef","Cutest bunny","s00000001"
"I do not know :-(","Cutest bunny","s00000002"
'''
GRADING_RESPONSE = '[{"pass": true, "motivation": "great answer"}]'
VALIDATION_RESPONSE = 'Amazing quiz. Just perfect.'


# This is just a hack to backport this option, which doesn't exist in PR yet
config.default_model = 'medium'


class TestQuizzesGradingAPI(BaseRoutesTestCase):
        
    def test_basics(self):
        # Listing should be empty
        response = self.client.get('/api/quizzes/list')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json) == 0
        # Create a new quizz
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
        print(response.json)
        
    def test_grading(self):
        
        def _dummy_grader(*args):
            time.sleep(.1)
            return GRADING_RESPONSE
        
        _dummy_model.DummyModel.invoke = _dummy_grader
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
            assert attempt['feedback'][0]['motivation'] == 'great answer'
        jsonschema.validate(response.json, json_schemas.QUIZ)
        # Check that state is has_scores
        response = self.client.get('/api/quizzes/state/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json['state'] == 'has_scores'

    def test_validation(self):
            
        # Install dummy validator
        def _dummy_validator(*args):
            time.sleep(.1)            
            return VALIDATION_RESPONSE
        _dummy_model.DummyModel.invoke = _dummy_validator        
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
        assert VALIDATION_RESPONSE in response.json['validation']
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
