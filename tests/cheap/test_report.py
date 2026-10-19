from .test_quizzes_api import DUMMY_QUIZ_DATA, DUMMY_ATTEMPTS
from heymans import report, convert
import csv
import json
import tempfile
from pathlib import Path


class TestReport:
    
    def get_quiz_data(self):
        quiz_data = json.loads(
            (Path(__file__).parent / 'testdata/quiz-data.json').read_text())
        # Only keep 10 attempts to speed up testing
        for question in quiz_data['questions']:
            question['attempts'] = question['attempts'][:10]
        return quiz_data
    
    def test_grading_pipeline(self):
        quiz_data = self.get_quiz_data()
        errors = report.check_grading_errors(quiz_data)
        assert errors is None
        dm = report.analyze_difficulty_and_discrimination(quiz_data)
        if hasattr(dm, 'column_names'):
            assert 'rir' in dm.column_names
        else:
            assert 'rir' in dm.columns
        dm = report.calculate_grades(quiz_data, dst='output/grades.csv')
        if hasattr(dm, 'column_names'):
            assert 'grade' in dm.column_names
        else:
            assert 'grade' in dm.columns
        dm = report.get_detailed_scores(quiz_data,
                                        dst='output/detailed-scores.csv')
        tmp_folder = tempfile.mkdtemp()
        report.generate_feedback(quiz_data, output_folder=tmp_folder)
        
    def test_validate_exam(self):
    
        quiz_data = self.get_quiz_data()
        output = report.validate_exam(quiz_data, model='dummy')
        assert 'Awesome question' in output
        
    def test_analyze_qualitative_errors(self):
    
        quiz_data = self.get_quiz_data()
        output = report.analyze_qualitative_errors(quiz_data, model='dummy')        
        assert 'Awesome question' in output
            
    def test_calculate_finished(self):
    
        def conversations(*username_finished):
            return [{'username': username, 'finished': finished}
                    for username, finished in username_finished]
    
        quiz_a = {
            'interactive_quiz_id': 11,
            'name': 'Quiz A',
            'conversations': conversations(
                ('student_b', False), ('student_a', True),
                ('student_a', False), ('student_a', True)),
        }
        # Single quiz
        dm = report.calculate_finished(quiz_a)
        assert list(dm.column_names) == ['quiz_id', 'quiz_name', 'username',
                                         'started', 'finished']
        assert list(dm.quiz_id) == [11, 11]
        assert list(dm.quiz_name) == ['Quiz A', 'Quiz A']
        assert list(dm.username) == ['student_a', 'student_b']
        assert list(dm.started) == [3, 1]
        assert list(dm.finished) == [2, 0]
        # Multiple quizzes, including a duplicate name and a quiz without
        # conversations, which should not be included.
        quiz_same_1 = {
            'interactive_quiz_id': 22, 'name': 'Same',
            'conversations': conversations(('student_a', True))}
        quiz_same_2 = {
            'interactive_quiz_id': 21, 'name': 'Same',
            'conversations': conversations(('student_a', False))}
        quiz_empty = {
            'interactive_quiz_id': 33, 'name': 'Empty', 'conversations': []}
        dm = report.calculate_finished(
            [quiz_same_1, quiz_empty, quiz_a, quiz_same_2])
        assert list(dm.quiz_id) == [11, 11, 21, 22]
        assert list(dm.quiz_name) == ['Quiz A', 'Quiz A', 'Same', 'Same']
        assert list(dm.username) == ['student_a', 'student_b', 'student_a',
                                     'student_a']
        assert list(dm.started) == [3, 1, 1, 1]
        assert list(dm.finished) == [2, 0, 0, 1]
        
    def test_calculate_finished_empty(self):
    
        for quiz_data in ([], {'interactive_quiz_id': 1, 'name': 'Quiz',
                                'conversations': []}):
            with tempfile.TemporaryDirectory() as tmp_folder:
                dst = Path(tmp_folder) / 'finished.csv'
                dm = report.calculate_finished(quiz_data, dst=dst)
                assert len(dm) == 0
                assert dst.read_text().strip() == \
                    'quiz_id,quiz_name,username,started,finished'
        
    def test_calculate_finished_csv(self):
    
        quiz_data = [{
            'interactive_quiz_id': 5,
            'name': 'Quiz, with "quotes"',
            'conversations': [{'username': 'student', 'finished': True}],
        }]
        with tempfile.TemporaryDirectory() as tmp_folder:
            dst = Path(tmp_folder) / 'finished.csv'
            report.calculate_finished(quiz_data, dst=dst)
            with dst.open(newline='') as f:
                rows = list(csv.DictReader(f))
        assert rows == [{'quiz_id': '5', 'quiz_name': 'Quiz, with "quotes"',
                         'username': 'student', 'started': '1',
                         'finished': '1'}]
            
    def test_grading_errors(self):
    
        quiz_info = convert.merge_brightspace_attempts(DUMMY_QUIZ_DATA,
                                                       DUMMY_ATTEMPTS)
        quiz_data = report.score(quiz_info, model='dummy')
        errors = report.check_grading_errors(quiz_data)        
        assert errors is None
