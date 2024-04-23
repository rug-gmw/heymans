import json
from http import HTTPStatus
from .test_app import BaseRoutesTestCase
from heymans import config


DUMMY_QUIZ_DATA = {
    'name': 'Quiz title',
    'questions': [
        {
            'question': 'Who is the cutest bunny?',
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


class TestQuizzesApi(BaseRoutesTestCase):
        
    def test_basics(self):
        # Listing should be empty
        response = self.client.get('/api/quizzes/list')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json) == 0
        # Create a new quizz
        response = self.client.post('/api/quizzes/new', json=DUMMY_QUIZ_DATA)
        assert response.status_code == HTTPStatus.OK
        assert response.json['quizId'] == 1
        # Check if the new quiz matches the dummy data that is was created with
        response = self.client.get('/api/quizzes/get/1')
        assert response.status_code == HTTPStatus.OK
        assert self.compare_dicts_ignore_none(response.json, DUMMY_QUIZ_DATA)
        # Listing should now have one quiz
        response = self.client.get('/api/quizzes/list')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json) == 1
        
    def xtest_grading(self):
        response = self.client.get('/api/quizzes/grading/poll/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json == 'needs_grading'
        response = self.client.post('/api/quizzes/grading/start', json={
            'quiz_id': 1,
            'prompt': 'Dummy prompt',
            'model': 'mistral'
        })
        assert response.status_code == HTTPStatus.NO_CONTENT
        response = self.client.get('/api/quizzes/grading/poll/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json == 'grading_in_progress'
        response = self.client.get('/api/quizzes/grading/poll/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json == 'grading_in_progress'
        response = self.client.get('/api/quizzes/grading/poll/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json == 'grading_done'
        response = self.client.get('/api/quizzes/get/1')
        assert response.status_code == HTTPStatus.OK
        for attempt in response.json['questions'][0]['attempts']:
            assert attempt['score'] == 1
            assert attempt['feedback'] == 'test feedback'

    def xtest_4_push_to_learning_environment(self):
        response = self.client.get(
            '/api/quizzes/grading/push_to_learning_environment/1')
        assert response.status_code == HTTPStatus.FORBIDDEN
