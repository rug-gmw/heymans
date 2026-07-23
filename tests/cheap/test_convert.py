import pytest
from pathlib import Path
from heymans import convert

exam_markdown_text = Path(__file__).parent / 'testdata/exam-markdown-questions.md'
exam_markdown_invalid_text = Path(__file__).parent / 'testdata/exam-markdown-invalid-questions.md'
exam_output_dict = {
    'name': 'PSB3E-CP08 Resit',
    'questions': [
        {
            'name': 'Dual process theory',
            'text': "In Haidt's model of moral decision making, which kind of mental processes (or system) typically comes first, and which kind of mental processes (or system) is used mainly to justify our initial response?",
            'answer_key': [
                'Intuitive (System 1) processes come first',
                'Reasoning (System 2) processes mainly serve to justify our intuitive responses'
            ]
        },
        {
            'name': 'Gambling',
            'text': 'Imagine that you can choose between two options:\n\nA) A guaranteed win of €50\nB) A 50% chance to win €150 and a 50% chance to lose €25\n\nMost people would choose option A. Which two psychological phenomena explain this preference?',
            'answer_key': [
                'Loss aversion explains that people weigh potential losses more heavily than equivalent possible gains',
                'Risk aversion explains that people prefer the certain outcome over the uncertain one, even when the expected value is lower'
            ]
        }
    ],
    'quiz_id': 1
}
exam_brightspace_text = '''NewQuestion,WR,HTML,,
ID,PSB3E-CP08 Resit-1,HTML,,
Title,"Dual process theory",HTML,,
QuestionText,"In Haidt's model of moral decision making, which kind of mental processes (or system) typically comes first, and which kind of mental processes (or system) is used mainly to justify our initial response?",HTML,,
Points,2,,,
AnswerKey,"- Intuitive (System 1) processes come first<br>- Reasoning (System 2) processes mainly serve to justify our intuitive responses",HTML,,
Feedback,"- Intuitive (System 1) processes come first<br>- Reasoning (System 2) processes mainly serve to justify our intuitive responses",HTML,,
NewQuestion,WR,HTML,,
ID,PSB3E-CP08 Resit-2,HTML,,
Title,"Gambling",HTML,,
QuestionText,"Imagine that you can choose between two options:<br><br>A) A guaranteed win of €50<br>B) A 50% chance to win €150 and a 50% chance to lose €25<br><br>Most people would choose option A. Which two psychological phenomena explain this preference?",HTML,,
Points,2,,,
AnswerKey,"- Loss aversion explains that people weigh potential losses more heavily than equivalent possible gains<br>- Risk aversion explains that people prefer the certain outcome over the uncertain one, even when the expected value is lower",HTML,,
Feedback,"- Loss aversion explains that people weigh potential losses more heavily than equivalent possible gains<br>- Risk aversion explains that people prefer the certain outcome over the uncertain one, even when the expected value is lower",HTML,,'''


def test_from_markdown_exam():
    assert convert.from_markdown_exam(exam_markdown_text, quiz_id=1) == exam_output_dict
    with pytest.raises(ValueError):
        convert.from_markdown_exam(exam_markdown_invalid_text, quiz_id=1)


def test_from_markdown_exam_rejects_en_dash_answer_keys():
    exam = '''# Exam

## Question

What is the answer?

– First answer key point
– Second answer key point
'''
    with pytest.raises(convert.MarkdownExamParseError) as exc_info:
        convert.from_markdown_exam(exam, quiz_id=1)
    assert 'lookalike dash characters' in exc_info.value.message
    assert exc_info.value.question_name == 'Question'
    assert 'regular hyphen' in exc_info.value.hint


def test_merge_brightspace_attempts_rejects_missing_required_columns():
    attempts = '''Answer
"The answer"
'''

    with pytest.raises(convert.BrightspaceAttemptsMergeError) as exc_info:
        convert.merge_brightspace_attempts(exam_markdown_text, attempts)

    assert 'missing required Brightspace columns' in exc_info.value.message
    assert 'Username' in exc_info.value.context
    assert 'Q Title or Q Text' in exc_info.value.context


def test_merge_brightspace_attempts_rejects_zero_matches():
    attempts = '''Answer,Q Title,Username
"The answer","Different question","s00000001"
'''

    with pytest.raises(convert.BrightspaceAttemptsMergeError) as exc_info:
        convert.merge_brightspace_attempts(exam_markdown_text, attempts)

    assert exc_info.value.message == 'No attempts matched the quiz questions.'
    assert 'Q Title' in exc_info.value.hint
    assert 'Q Text' in exc_info.value.hint


def test_merge_brightspace_attempts_matches_q_text_without_q_title():
    attempts = '''Answer,Q Text,Username
"The answer","In Haidt's model of moral decision making, which kind of mental processes (or system) typically comes first, and which kind of mental processes (or system) is used mainly to justify our initial response?","s00000001"
'''

    quiz = convert.merge_brightspace_attempts(exam_markdown_text, attempts)

    assert len(quiz['questions'][0]['attempts']) == 1
    assert quiz['questions'][0]['attempts'][0]['username'] == 's00000001'
    assert quiz['questions'][0]['attempts'][0]['answer'] == 'The answer'
    


def test_to_brightspace_exam():
    assert convert.to_brightspace_exam(exam_markdown_text,
                                       points_per_question=None) == exam_brightspace_text
