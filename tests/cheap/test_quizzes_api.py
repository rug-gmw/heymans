import json
from http import HTTPStatus
from .test_app import BaseRoutesTestCase
from heymans import config
from sigmund.model import _dummy_model


DUMMY_QUIZ_DATA = {
    'name': 'Quiz title',
    'questions': [
        {
            'text': 'Who is the cutest bunny?',
            'answer_key': '- Must state that the cutest bunny is Boef',
            'attempts': [{
                'username': 's12345678',
                'answer': 'The cutest bunny is Boef',
            }, {
                'username': 's12345678',
                'answer': 'Don\'t know. :-('
            }]
        }
    ]
}


class TestQuizzesAPI(BaseRoutesTestCase):
        
    def test_basics(self):
        # Listing should be empty
        response = self.client.get('/api/quizzes/list')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json) == 0
        # Create a new quizz
        response = self.client.post('/api/quizzes/new', json=DUMMY_QUIZ_DATA)
        assert response.status_code == HTTPStatus.OK
        assert response.json['quiz_id'] == 1
        # Check if the new quiz matches the dummy data that is was created with
        response = self.client.get('/api/quizzes/get/1')
        assert response.status_code == HTTPStatus.OK
        assert self.compare_dicts_ignore_none(response.json, DUMMY_QUIZ_DATA)
        # Listing should now have one quiz
        response = self.client.get('/api/quizzes/list')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json) == 1
        
    def test_grading(self):
        
        def _dummy_grader(*args):
            import time
            time.sleep(.1)
            return '[{"pass": 1, "feedback": "dummy feedback"}]'
        
        _dummy_model.DummyModel.invoke = _dummy_grader
        # Create a new quizz
        response = self.client.post('/api/quizzes/new', json=DUMMY_QUIZ_DATA)
        assert response.status_code == HTTPStatus.OK
        assert response.json['quiz_id'] == 1
        # Check that the quiz needs grading
        response = self.client.get('/api/quizzes/grading/poll/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json['message'] == 'needs_grading'
        # Start grading
        response = self.client.post('/api/quizzes/grading/start', json={
            'quiz_id': 1,
            'model': 'dummy'
        })
        assert response.status_code == HTTPStatus.NO_CONTENT
        # Grading should now be in progress
        response = self.client.get('/api/quizzes/grading/poll/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json['message'] == 'grading_in_progress'
        import time
        time.sleep(1)
        # Grading should now be done
        response = self.client.get('/api/quizzes/grading/poll/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json['message'] == 'grading_done'
        response = self.client.get('/api/quizzes/get/1')
        assert response.status_code == HTTPStatus.OK
        for attempt in response.json['questions'][0]['attempts']:
            assert attempt['score'] == 1
            assert json.loads(attempt['feedback'])[0]['feedback'] == \
                'dummy feedback'
