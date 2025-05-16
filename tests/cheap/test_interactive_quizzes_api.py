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
        path = Path(__file__).parent / 'testdata/test.docx'
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
        # Check if the new quiz matches the dummy data that is was created with
        response = self.client.get('/api/interactive_quizzes/get/1')
        assert response.status_code == HTTPStatus.OK
        # Listing should now have one quiz
        response = self.client.get('/api/interactive_quizzes/list')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json) == 1
        # Delete the one quiz
        response = self.client.delete('/api/interactive_quizzes/delete/1')
        assert response.status_code == HTTPStatus.NO_CONTENT
        # Listing should now have no quizzes
        response = self.client.get('/api/interactive_quizzes/list')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json) == 0
