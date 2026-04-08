import json
from http import HTTPStatus
from pathlib import Path
from .test_app import BaseRoutesTestCase


class TestInteractiveQuizzesAPI(BaseRoutesTestCase):
        
    def test_basics(self):
        
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
        interactive_quiz_id = response.json['interactive_quiz_id']
        # Check if the new quiz exists
        response = self.client.get(f'/api/interactive_quizzes/get/{interactive_quiz_id}')
        assert response.status_code == HTTPStatus.OK
        # Listing should now have one quiz
        response = self.client.get('/api/interactive_quizzes/list')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json) == 1
        # The user should not have any finished quizzes
        response = self.client.post(
            f'/api/interactive_quizzes/user/finished/{interactive_quiz_id}',
            json={'username': 'dummy user'})
        assert response.status_code == HTTPStatus.OK
        assert response.json['finished'] == 0
        # Start conversation
        response = self.client.post(
            f'/api/interactive_quizzes/conversation/start/{interactive_quiz_id}',
            json={'username': 'dummy user'})
        assert response.status_code == HTTPStatus.OK
        assert response.json['conversation_id'] == 1
        token = response.json['token']
        # Send message to conversation
        response = self.client.post(
            '/api/interactive_quizzes/conversation/send_message/1',
            json={"text": "<NOT_FINISHED>", "model": "dummy", "token": token})
        assert response.status_code == HTTPStatus.OK
        assert not response.json['finished']
        # Send message to conversation
        response = self.client.post(
            '/api/interactive_quizzes/conversation/send_message/1',
            json={"text": "<FINISHED>", "model": "dummy", "token": token})
        assert response.status_code == HTTPStatus.OK
        # Check if the quiz now has a finished conversation
        response = self.client.get(f'/api/interactive_quizzes/get/{interactive_quiz_id}')
        assert response.status_code == HTTPStatus.OK
        conversation = response.json['conversations'][0]
        assert conversation['username'] == 'dummy user'
        assert conversation['finished']
        # The user should now have one finished quiz
        response = self.client.post(
            f'/api/interactive_quizzes/user/finished/{interactive_quiz_id}',
            json={'username': 'dummy user'})
        assert response.status_code == HTTPStatus.OK
        assert response.json['finished'] == 1
        # Check the export functionality
        response = self.client.get(f'/api/interactive_quizzes/export/finished/{interactive_quiz_id}')
        assert response.status_code == HTTPStatus.OK
        assert response.json['content'].strip() == '''finished,started,username
1,1,dummy user'''        
        # Rename quiz
        response = self.client.post(f'/api/interactive_quizzes/rename/{interactive_quiz_id}',
                                    json={"name": "New name"})
        assert response.status_code == HTTPStatus.NO_CONTENT
        
        response = self.client.get(f'/api/interactive_quizzes/get/{interactive_quiz_id}')
        assert response.status_code == HTTPStatus.OK
        assert response.json['name'] == 'New name'
        # Delete the one quiz
        response = self.client.delete(f'/api/interactive_quizzes/delete/{interactive_quiz_id}')
        assert response.status_code == HTTPStatus.NO_CONTENT
        # Listing should now have no quizzes
        response = self.client.get('/api/interactive_quizzes/list')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json) == 0
