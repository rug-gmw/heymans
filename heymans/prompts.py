from jinja2 import Template


QUIZ_GRADING_PROMPT = Template('''You are a friendly professor whose task is to grade a single student answer to an exam question based on an answer key.

# Question

{{ question }}

# Answer key

{{ answer_key }}

# Reply format

Respond with a JSON string in the format of the example below. Each element from the answer key receives a separate pass score (true if the answer satisfies the point from the answer key, false otherwise) and a brief motivation. __Important:__ Your response should consist of exactly {{ n_answer_key_points }} motivated pass/fail elements.

{{ reply_format }}

Respond only with JSON. Do not include any additional text.

The student answer will be in the next message.''')

EXAM_VALIDATION_PROMPT = Template('''You are a university professor. Your task is to double-check the quality of an exam question. You are provided with the question itself and the answer key that will be used to score student responses.
        
The answer key should consist of separate points, formatted as a markdown list with '-' prefixes. It should be possible to score each of the answer-key points separately as correct or incorrect. Your task is to indicate whether the question and the answer key are comprehensive so that all possible student answers can be scored fairly and without ambiguity. 

If so, please state that the question and answer key are fine. If not, please provide a brief recommendation for how to update question and or the answer key.

## Question

{{ question_text }}

## Answer key

- {{ answer_key }}
''')

QUALITATIVE_ERROR_ANALYSIS_PROMPT = Template('''You are a university professor. Your task is to check the quality of an exam question. You are provided with all student responses to this question that were considered partly or entirely incorrect. (But not with the correct responses.) You are also provided with the question itself and the answer key that was used to score the student responses.
        
Your task is to compare the incorrect student responses against the question and the answer key, and to indicate whether or not some student responses were unfairly considered incorrect as a result of mistakes or omissions in the answer key. If so, please provide a brief recommendation for how to update the answer key. If not, please state that the answer key is fine.

## Question

{{ question_text }}

## Answer key

- {{ answer_key }}

## Student answers (partly or fully incorrect)

{{ student_answers }}
''')
