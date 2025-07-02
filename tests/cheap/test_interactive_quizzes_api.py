import json
from http import HTTPStatus
from pathlib import Path
from .test_app import BaseRoutesTestCase
from sigmund.model import _dummy_model


class TestInteractiveQuizzesAPI(BaseRoutesTestCase):
        
    def test_basics(self):
        
        def _dummy_responder(self, messages):
            """Just echo the last message"""
            return messages[-1].content
        
        _dummy_model.DummyModel.invoke = _dummy_responder        
        
        # Listing should be empty
        response = self.client.get('/api/interactive_quizzes/list')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json) == 0
        # Add a document for the quiz
        path = Path(__file__).parent / 'testdata/test_source.md'
        with path.open('rb') as file:
            document_info = {'public': True}
            data = {'json': json.dumps(document_info),
                    'file': (file, path.name)}
            response = self.client.post('/api/documents/add', data=data)
        assert response.status_code == HTTPStatus.OK
        document_id = response.json['document_id']
        # Create a new quiz
        response = self.client.post('/api/interactive_quizzes/new',
            json={'name': 'Test', 'public': False, 'document_id': document_id})
        assert response.status_code == HTTPStatus.OK
        assert response.json['interactive_quiz_id'] == 1
        # Check if the new quiz exists
        response = self.client.get('/api/interactive_quizzes/get/1')
        assert response.status_code == HTTPStatus.OK
        # Listing should now have one quiz
        response = self.client.get('/api/interactive_quizzes/list')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json) == 1
        # Start conversation
        response = self.client.get(
            '/api/interactive_quizzes/conversation/start/1')
        assert response.status_code == HTTPStatus.OK
        assert response.json['conversation_id'] == 1
        # Send message to conversation
        response = self.client.post(
            '/api/interactive_quizzes/conversation/send_message/1',
            json={"text": "<NOT_FINISHED>", "model": "dummy"})
        assert response.status_code == HTTPStatus.OK
        assert not response.json['finished']
        # Send message to conversation
        response = self.client.post(
            '/api/interactive_quizzes/conversation/send_message/1',
            json={"text": "<FINISHED>", "model": "dummy"})
        assert response.status_code == HTTPStatus.OK
        assert response.json['finished']
        # Check if the quiz not has a finished conversation
        response = self.client.get('/api/interactive_quizzes/get/1')
        assert response.status_code == HTTPStatus.OK
        conversation = response.json['conversations'][0]
        assert conversation['finished']
        assert conversation['username'] == 'test@test.com'
        assert conversation['user_id'] == 'dummy'
        # Delete the one quiz
        response = self.client.delete('/api/interactive_quizzes/delete/1')
        assert response.status_code == HTTPStatus.NO_CONTENT
        # Listing should now have no quizzes
        response = self.client.get('/api/interactive_quizzes/list')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json) == 0
