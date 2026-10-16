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

    def test_quiz_dates_lifecycle(self):
        """Dates can be set on creation, updated, and cleared; changing
        them does not clear existing conversations."""
        # Add a document for the quiz
        path = Path(__file__).parent / 'testdata/test_source.md'
        with path.open('rb') as file:
            data = {'json': json.dumps({'public': True}),
                    'file': (file, path.name)}
            response = self.client.post('/api/documents/add', data=data)
        assert response.status_code == HTTPStatus.OK
        document_id = response.json['document_id']
        # Create a quiz with a start and end date. The timezone offset in
        # the start date should be normalized to UTC.
        response = self.client.post('/api/interactive_quizzes/new',
            json={
                'name': 'Dated quiz',
                'public': False,
                'document_id': document_id,
                'start_date': '2020-01-01T02:00:00+02:00',
                'end_date': '2030-01-01T00:00:00',
            })
        assert response.status_code == HTTPStatus.OK
        interactive_quiz_id = response.json['interactive_quiz_id']
        # The dates should be returned by get as naive UTC ISO strings
        response = self.client.get(
            f'/api/interactive_quizzes/get/{interactive_quiz_id}')
        assert response.status_code == HTTPStatus.OK
        assert response.json['start_date'] == '2020-01-01T00:00:00'
        assert response.json['end_date'] == '2030-01-01T00:00:00'
        # The list should include the dates and an is_open flag
        response = self.client.get('/api/interactive_quizzes/list')
        assert response.status_code == HTTPStatus.OK
        entry = next(quiz for quiz in response.json
                     if quiz['quiz_id'] == interactive_quiz_id)
        assert entry['start_date'].startswith('2020-01-01T00:00:00')
        assert entry['end_date'].startswith('2030-01-01T00:00:00')
        assert entry['is_open'] is True
        # A partial settings update leaves the absent date unchanged
        response = self.client.post(
            f'/api/interactive_quizzes/settings/{interactive_quiz_id}',
            json={'end_date': '2031-01-01T00:00:00'})
        assert response.status_code == HTTPStatus.OK
        assert response.json['start_date'].startswith('2020-01-01T00:00:00')
        assert response.json['end_date'].startswith('2031-01-01T00:00:00')
        # Start a conversation, then clear the end date with null; this
        # should not clear existing conversations
        response = self.client.post(
            f'/api/interactive_quizzes/conversation/start/{interactive_quiz_id}',
            json={'username': 'dummy user'})
        assert response.status_code == HTTPStatus.OK
        response = self.client.post(
            f'/api/interactive_quizzes/settings/{interactive_quiz_id}',
            json={'end_date': None})
        assert response.status_code == HTTPStatus.OK
        assert response.json['end_date'] is None
        response = self.client.get(
            f'/api/interactive_quizzes/get/{interactive_quiz_id}')
        assert response.status_code == HTTPStatus.OK
        assert response.json['end_date'] is None
        assert response.json['start_date'] == '2020-01-01T00:00:00'
        assert len(response.json['conversations']) == 1

    def test_invalid_dates_are_rejected(self):
        # Add a document for the quiz
        path = Path(__file__).parent / 'testdata/test_source.md'
        with path.open('rb') as file:
            data = {'json': json.dumps({'public': True}),
                    'file': (file, path.name)}
            response = self.client.post('/api/documents/add', data=data)
        assert response.status_code == HTTPStatus.OK
        document_id = response.json['document_id']
        # An end date before the start date is rejected
        response = self.client.post('/api/interactive_quizzes/new',
            json={
                'name': 'Invalid quiz',
                'public': False,
                'document_id': document_id,
                'start_date': '2030-01-02T00:00:00',
                'end_date': '2030-01-01T00:00:00',
            })
        assert response.status_code == HTTPStatus.BAD_REQUEST
        # A date that is not in ISO 8601 format is rejected as well
        response = self.client.post('/api/interactive_quizzes/new',
            json={
                'name': 'Invalid quiz',
                'public': False,
                'document_id': document_id,
                'start_date': 'tomorrow',
            })
        assert response.status_code == HTTPStatus.BAD_REQUEST
        # The same checks apply when updating settings
        response = self.client.post('/api/interactive_quizzes/new',
            json={'name': 'Valid quiz', 'public': False,
                  'document_id': document_id})
        assert response.status_code == HTTPStatus.OK
        interactive_quiz_id = response.json['interactive_quiz_id']
        response = self.client.post(
            f'/api/interactive_quizzes/settings/{interactive_quiz_id}',
            json={'start_date': '2030-01-02T00:00:00',
                  'end_date': '2030-01-01T00:00:00'})
        assert response.status_code == HTTPStatus.BAD_REQUEST
        response = self.client.post(
            f'/api/interactive_quizzes/settings/{interactive_quiz_id}',
            json={'start_date': 'tomorrow'})
        assert response.status_code == HTTPStatus.BAD_REQUEST
        # The invalid settings should not have been applied
        response = self.client.get(
            f'/api/interactive_quizzes/get/{interactive_quiz_id}')
        assert response.status_code == HTTPStatus.OK
        assert response.json['start_date'] is None
        assert response.json['end_date'] is None

    def test_conversation_start_respects_dates(self):
        # Add a document for the quiz
        path = Path(__file__).parent / 'testdata/test_source.md'
        with path.open('rb') as file:
            data = {'json': json.dumps({'public': True}),
                    'file': (file, path.name)}
            response = self.client.post('/api/documents/add', data=data)
        assert response.status_code == HTTPStatus.OK
        document_id = response.json['document_id']
        # A quiz whose end date has passed can no longer be started
        response = self.client.post('/api/interactive_quizzes/new',
            json={'name': 'Closed quiz', 'public': False,
                  'document_id': document_id,
                  'start_date': '2020-01-01T00:00:00',
                  'end_date': '2021-01-01T00:00:00'})
        assert response.status_code == HTTPStatus.OK
        closed_quiz_id = response.json['interactive_quiz_id']
        response = self.client.post(
            f'/api/interactive_quizzes/conversation/start/{closed_quiz_id}',
            json={'username': 'dummy user'})
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert 'closed' in response.json['error']
        # A quiz that has not opened yet cannot be started
        response = self.client.post('/api/interactive_quizzes/new',
            json={'name': 'Future quiz', 'public': False,
                  'document_id': document_id,
                  'start_date': '2030-01-01T00:00:00'})
        assert response.status_code == HTTPStatus.OK
        future_quiz_id = response.json['interactive_quiz_id']
        response = self.client.post(
            f'/api/interactive_quizzes/conversation/start/{future_quiz_id}',
            json={'username': 'dummy user'})
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert 'not opened' in response.json['error']
        # A quiz inside its window can be started
        response = self.client.post('/api/interactive_quizzes/new',
            json={'name': 'Open quiz', 'public': False,
                  'document_id': document_id,
                  'start_date': '2020-01-01T00:00:00',
                  'end_date': '2030-01-01T00:00:00'})
        assert response.status_code == HTTPStatus.OK
        open_quiz_id = response.json['interactive_quiz_id']
        response = self.client.post(
            f'/api/interactive_quizzes/conversation/start/{open_quiz_id}',
            json={'username': 'dummy user'})
        assert response.status_code == HTTPStatus.OK

    def test_send_message_blocked_after_deadline(self):
        # Add a document for the quiz
        path = Path(__file__).parent / 'testdata/test_source.md'
        with path.open('rb') as file:
            data = {'json': json.dumps({'public': True}),
                    'file': (file, path.name)}
            response = self.client.post('/api/documents/add', data=data)
        assert response.status_code == HTTPStatus.OK
        document_id = response.json['document_id']
        # Create an open quiz and start a conversation
        response = self.client.post('/api/interactive_quizzes/new',
            json={'name': 'Open quiz', 'public': False,
                  'document_id': document_id,
                  'end_date': '2030-01-01T00:00:00'})
        assert response.status_code == HTTPStatus.OK
        interactive_quiz_id = response.json['interactive_quiz_id']
        response = self.client.post(
            f'/api/interactive_quizzes/conversation/start/{interactive_quiz_id}',
            json={'username': 'dummy user'})
        assert response.status_code == HTTPStatus.OK
        conversation_id = response.json['conversation_id']
        token = response.json['token']
        # The teacher closes the quiz while the conversation is in flight
        response = self.client.post(
            f'/api/interactive_quizzes/settings/{interactive_quiz_id}',
            json={'end_date': '2020-01-01T00:00:00'})
        assert response.status_code == HTTPStatus.OK
        # No further messages are accepted, even with a valid token
        response = self.client.post(
            f'/api/interactive_quizzes/conversation/send_message/{conversation_id}',
            json={'text': 'hello', 'model': 'dummy', 'token': token})
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert 'closed' in response.json['error']
