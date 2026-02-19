import json
from http import HTTPStatus
from pathlib import Path
from .test_app import BaseRoutesTestCase


class TestDocumentsAPI(BaseRoutesTestCase):
        
    def test_basics(self):
        # Check that there are no documents
        response = self.client.get('/api/documents/list/1')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json) == 0
        # Add new document
        for path in (Path(__file__).parent / 'testdata').glob('test.*'):
            with path.open('rb') as file:
                document_info = {'public': True, 'name': 'test document'}
                data = {'json': json.dumps(document_info),
                        'file': (file, path.name)}
                response = self.client.post('/api/documents/add', data=data)
            assert response.status_code == HTTPStatus.OK
        # Check that there is one document
        response = self.client.get('/api/documents/list/1')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json) == 4
        assert response.json[0]['public']
        assert response.json[0]['name'] == 'test document'
        # Test automatic name suffixes
        assert response.json[1]['name'] == 'test document (1)'
        assert response.json[2]['name'] == 'test document (2)'
        # Change the public status of the first document
        response = self.client.post('/api/documents/update/1',
                                    json={'public': False})
        assert response.status_code == HTTPStatus.OK
        response = self.client.get('/api/documents/list/1')
        assert response.status_code == HTTPStatus.OK        
        assert len(response.json) == 4
        assert not response.json[0]['public']        
        assert response.json[0]['name'] == 'test document'
        # Get the document
        document_id = response.json[0]['document_id']
        response = self.client.get('api/documents/get/{}'.format(document_id))
        assert response.status_code == HTTPStatus.OK
        response = self.client.get('api/documents/get/999')
        assert response.status_code == HTTPStatus.NOT_FOUND
        # Change the name of the first document
        response = self.client.post('/api/documents/update/1',
                                    json={'name': 'new name'})
        assert response.status_code == HTTPStatus.OK
        response = self.client.get('/api/documents/list/1')
        assert response.status_code == HTTPStatus.OK        
        assert len(response.json) == 4
        assert not response.json[0]['public']
        assert response.json[0]['name'] == 'new name'
        # Delete the last document
        response = self.client.delete('/api/documents/delete/2')
        assert response.status_code == HTTPStatus.OK
        # List all documents
        response = self.client.get('/api/documents/list/1')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json) == 3
        assert not response.json[0]['public']
        assert response.json[1]['public']
