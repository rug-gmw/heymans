from pathlib import Path
from heymans import convert

exam_markdown_text = Path(__file__).parent / 'testdata/exam-markdown-questions.md'
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


def test_to_brightspace_exam():
    assert convert.to_brightspace_exam(exam_markdown_text,
                                       points_per_question=None) == exam_brightspace_text
