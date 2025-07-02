from .test_quizzes_api import DUMMY_QUIZ_DATA, DUMMY_ATTEMPTS, GRADING_RESPONSE
from heymans import report, convert
from sigmund.model import _dummy_model
import time


class TestQuizzesStandalone:
    
    def test_basics(self):
        
        def _dummy_grader(*args):
            time.sleep(.1)
            return GRADING_RESPONSE
        
        _dummy_model.DummyModel.invoke = _dummy_grader        
        quiz_info = convert.merge_brightspace_attempts(DUMMY_QUIZ_DATA,
                                                       DUMMY_ATTEMPTS)
        quiz_data = report.score(quiz_info, model='dummy')
        assert quiz_data['errors'] is None
        errors = report.check_grading_errors(quiz_data)
        assert errors is None
        
        def _error_grader(*args):
            time.sleep(.1)
            return "ERROR"
        
        _dummy_model.DummyModel.invoke = _error_grader
        quiz_info = convert.merge_brightspace_attempts(DUMMY_QUIZ_DATA,
                                                       DUMMY_ATTEMPTS)
        quiz_data = report.score(quiz_info, model='dummy')
        assert quiz_data['errors']
        errors = report.check_grading_errors(quiz_data)
        print(errors)
        assert errors is not None
        