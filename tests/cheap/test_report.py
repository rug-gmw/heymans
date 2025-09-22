from .test_quizzes_api import DUMMY_QUIZ_DATA, DUMMY_ATTEMPTS
from heymans import report, convert
from sigmund.model import _dummy_model
import time
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
            
    def test_grading_errors(self):
    
        quiz_info = convert.merge_brightspace_attempts(DUMMY_QUIZ_DATA,
                                                       DUMMY_ATTEMPTS)
        quiz_data = report.score(quiz_info, model='dummy')
        errors = report.check_grading_errors(quiz_data)        
        assert errors is None
