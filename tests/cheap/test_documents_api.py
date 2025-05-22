import json
import os
from http import HTTPStatus
from pathlib import Path
from .test_app import BaseRoutesTestCase
from heymans import config


class TestDocumentsAPI(BaseRoutesTestCase):
        
    def test_basics(self):
        # Add new document
        for path in (Path(__file__).parent / 'testdata').glob('test.*'):
            with path.open('rb') as file:
                document_info = {'public': True}
                data = {'json': json.dumps(document_info),
                        'file': (file, path.name)}
                response = self.client.post('/api/documents/add', data=data)
            assert response.status_code == HTTPStatus.OK
            document_id = response.json['document_id']
        # Change the public status of the first document
        response = self.client.post('/api/documents/update/1',
                                    json={'public': False})
        assert response.status_code == HTTPStatus.OK
        # Delete the last document
        response = self.client.delete('/api/documents/delete/2')
        assert response.status_code == HTTPStatus.OK
        # List all documents
        response = self.client.get('/api/documents/list/1')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json) == 2
        assert not response.json[0]['public']
        assert response.json[1]['public']
