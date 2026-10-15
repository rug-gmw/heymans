import csv
import io
import json
from http import HTTPStatus
from pathlib import Path
from heymans.database.operations import interactive_quizzes as iq_ops, \
    users as users_ops
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
            json={
                'name': 'Test',
                'public': False,
                'document_id': document_id,
                'enabled_skills': ['understand', 'analyze'],
            })
        assert response.status_code == HTTPStatus.OK
        interactive_quiz_id = response.json['interactive_quiz_id']
        # Check if the new quiz exists
        response = self.client.get(f'/api/interactive_quizzes/get/{interactive_quiz_id}')
        assert response.status_code == HTTPStatus.OK
        assert response.json['enabled_skills'] == ['understand', 'analyze']
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
        # Quiz should have name
        response = self.client.get(f'/api/interactive_quizzes/name/{interactive_quiz_id}')
        assert response.status_code == HTTPStatus.OK
        assert response.json['name'] == 'Test'
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
        assert response.json['content'].strip() == f'''quiz_id,quiz_name,username,started,finished
{interactive_quiz_id},Test,dummy user,1,1'''
        # Exporting without a quiz id exports all quizzes of this user
        response = self.client.get('/api/interactive_quizzes/export/finished')
        assert response.status_code == HTTPStatus.OK
        assert response.json['content'].strip() == f'''quiz_id,quiz_name,username,started,finished
{interactive_quiz_id},Test,dummy user,1,1'''
        # Rename quiz
        response = self.client.post(f'/api/interactive_quizzes/rename/{interactive_quiz_id}',
                                    json={"name": "New name"})
        assert response.status_code == HTTPStatus.OK
        assert response.json == {
            'interactive_quiz_id': interactive_quiz_id,
            'name': 'New name',
        }

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

    def _add_document(self):
        path = Path(__file__).parent / 'testdata/test_source.md'
        with path.open('rb') as file:
            document_info = {'public': True}
            data = {'json': json.dumps(document_info), 'file': (file, path.name)}
            response = self.client.post('/api/documents/add', data=data)
        assert response.status_code == HTTPStatus.OK
        return response.json['document_id']

    def _new_quiz(self, name, document_id):
        response = self.client.post(
            '/api/interactive_quizzes/new',
            json={'name': name, 'public': False, 'document_id': document_id},
        )
        assert response.status_code == HTTPStatus.OK
        return response.json['interactive_quiz_id']

    def _start_conversation(self, interactive_quiz_id, username,
                            finish=False):
        response = self.client.post(
            f'/api/interactive_quizzes/conversation/start/{interactive_quiz_id}',
            json={'username': username})
        assert response.status_code == HTTPStatus.OK
        if not finish:
            return
        conversation_id = response.json['conversation_id']
        response = self.client.post(
            f'/api/interactive_quizzes/conversation/send_message/{conversation_id}',
            json={'text': '<FINISHED>', 'model': 'dummy',
                  'token': response.json['token']})
        assert response.status_code == HTTPStatus.OK

    def _export_rows(self, url='/api/interactive_quizzes/export/finished'):
        response = self.client.get(url)
        assert response.status_code == HTTPStatus.OK
        reader = csv.DictReader(io.StringIO(response.json['content']))
        return reader.fieldnames, list(reader)

    def test_export_all_without_quizzes(self):
        fieldnames, rows = self._export_rows()
        assert fieldnames == ['quiz_id', 'quiz_name', 'username', 'started',
                              'finished']
        assert rows == []

    def test_export_all_quizzes(self):
        document_id = self._add_document()
        # Quizzes are deliberately created out of alphabetical order. Two
        # quizzes share a name, so the quiz_id is needed to tell them apart.
        beta_id = self._new_quiz('Beta', document_id)
        alpha_id = self._new_quiz('Alpha', document_id)
        same_1_id = self._new_quiz('Same', document_id)
        same_2_id = self._new_quiz('Same', document_id)
        empty_id = self._new_quiz('Empty', document_id)
        self._start_conversation(alpha_id, 'student_b')
        self._start_conversation(alpha_id, 'student_a', finish=True)
        self._start_conversation(alpha_id, 'student_a')
        self._start_conversation(beta_id, 'student_a', finish=True)
        self._start_conversation(same_1_id, 'student_a', finish=True)
        self._start_conversation(same_2_id, 'student_a')
        # A public quiz of a different user should not be exported
        users_ops.create_user_if_not_exists(username='other@test.com',
                                            user_id='other')
        other_id = iq_ops.new_interactive_quiz(
            name='Other', document_id=document_id, user_id='other',
            public=True)
        iq_ops.new_interactive_quiz_conversation(other_id, 'other_student',
                                                 'dummy')
        fieldnames, rows = self._export_rows()
        assert fieldnames == ['quiz_id', 'quiz_name', 'username', 'started',
                              'finished']
        # Ordered by quiz name, quiz id, and username. The quiz without
        # conversations and the quiz of the other user are not included.
        same_ids = sorted([same_1_id, same_2_id])
        expected_started_finished = {
            (alpha_id, 'student_a'): ('2', '1'),
            (alpha_id, 'student_b'): ('1', '0'),
            (beta_id, 'student_a'): ('1', '1'),
            (same_1_id, 'student_a'): ('1', '1'),
            (same_2_id, 'student_a'): ('1', '0'),
        }
        assert [(row['quiz_name'], int(row['quiz_id']), row['username'])
                for row in rows] == [
            ('Alpha', alpha_id, 'student_a'),
            ('Alpha', alpha_id, 'student_b'),
            ('Beta', beta_id, 'student_a'),
            ('Same', same_ids[0], 'student_a'),
            ('Same', same_ids[1], 'student_a'),
        ]
        for row in rows:
            key = int(row['quiz_id']), row['username']
            assert (row['started'], row['finished']) == \
                expected_started_finished[key]
        assert str(empty_id) not in [row['quiz_id'] for row in rows]
        assert str(other_id) not in [row['quiz_id'] for row in rows]
        # Exporting a single quiz gives only the rows for that quiz
        fieldnames, rows = self._export_rows(
            f'/api/interactive_quizzes/export/finished/{alpha_id}')
        assert [(row['quiz_name'], row['username'], row['started'],
                 row['finished']) for row in rows] == [
            ('Alpha', 'student_a', '2', '1'),
            ('Alpha', 'student_b', '1', '0'),
        ]

    def test_export_single_nonexistent_quiz(self):
        response = self.client.get('/api/interactive_quizzes/export/finished/1')
        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_logs_hide_seeded_opening_user_message(self):
        path = Path(__file__).parent / 'testdata/test_source.md'
        with path.open('rb') as file:
            document_info = {'public': True}
            data = {'json': json.dumps(document_info), 'file': (file, path.name)}
            response = self.client.post('/api/documents/add', data=data)
        assert response.status_code == HTTPStatus.OK
        document_id = response.json['document_id']

        response = self.client.post(
            '/api/interactive_quizzes/new',
            json={'name': 'Test logs', 'public': False, 'document_id': document_id},
        )
        assert response.status_code == HTTPStatus.OK
        interactive_quiz_id = response.json['interactive_quiz_id']

        response = self.client.post(
            f'/api/interactive_quizzes/conversation/start/{interactive_quiz_id}',
            json={'username': 'dummy user'},
        )
        assert response.status_code == HTTPStatus.OK

        response = self.client.get(
            f'/api/interactive_quizzes/logs/{interactive_quiz_id}/dummy%20user'
        )
        assert response.status_code == HTTPStatus.OK

        conversations = response.json['conversations']
        assert len(conversations) == 1
        assert conversations[0]['bloom_skill'] == 'understand'
        messages = conversations[0]['messages']
        assert len(messages) >= 1
        assert messages[0]['message_type'] == 'ai'
        assert all(message['text'] != 'Ask me anything!' for message in messages)

    def test_update_quiz_settings_enabled_skills(self):
        path = Path(__file__).parent / 'testdata/test_source.md'
        with path.open('rb') as file:
            document_info = {'public': True}
            data = {'json': json.dumps(document_info), 'file': (file, path.name)}
            response = self.client.post('/api/documents/add', data=data)
        assert response.status_code == HTTPStatus.OK
        document_id = response.json['document_id']

        response = self.client.post(
            '/api/interactive_quizzes/new',
            json={'name': 'Settings Quiz', 'public': False, 'document_id': document_id},
        )
        assert response.status_code == HTTPStatus.OK
        interactive_quiz_id = response.json['interactive_quiz_id']

        response = self.client.post(
            f'/api/interactive_quizzes/settings/{interactive_quiz_id}',
            json={'enabled_skills': ['evaluate', 'create']},
        )
        assert response.status_code == HTTPStatus.OK
        assert response.json['enabled_skills'] == ['evaluate', 'create']

        response = self.client.get(f'/api/interactive_quizzes/get/{interactive_quiz_id}')
        assert response.status_code == HTTPStatus.OK
        assert response.json['enabled_skills'] == ['evaluate', 'create']

    def test_update_quiz_settings_clears_existing_conversations(self):
        path = Path(__file__).parent / 'testdata/test_source.md'
        with path.open('rb') as file:
            document_info = {'public': True}
            data = {'json': json.dumps(document_info), 'file': (file, path.name)}
            response = self.client.post('/api/documents/add', data=data)
        assert response.status_code == HTTPStatus.OK
        document_id = response.json['document_id']

        response = self.client.post(
            '/api/interactive_quizzes/new',
            json={'name': 'Settings reset quiz', 'public': False, 'document_id': document_id},
        )
        assert response.status_code == HTTPStatus.OK
        interactive_quiz_id = response.json['interactive_quiz_id']

        response = self.client.post(
            f'/api/interactive_quizzes/conversation/start/{interactive_quiz_id}',
            json={'username': 'student_a'},
        )
        assert response.status_code == HTTPStatus.OK

        response = self.client.get(f'/api/interactive_quizzes/get/{interactive_quiz_id}')
        assert response.status_code == HTTPStatus.OK
        assert len(response.json['conversations']) == 1

        response = self.client.post(
            f'/api/interactive_quizzes/settings/{interactive_quiz_id}',
            json={'enabled_skills': ['evaluate']},
        )
        assert response.status_code == HTTPStatus.OK

        response = self.client.get(f'/api/interactive_quizzes/get/{interactive_quiz_id}')
        assert response.status_code == HTTPStatus.OK
        assert response.json['conversations'] == []
