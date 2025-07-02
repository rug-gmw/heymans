"""
# Heymans example workflow for Brightspace

This notebook provides an example workflow for using Heymans as a Python library to grade open-ended exams in combination with the Brightspace learning environment.

The example data is based on real exam questions and student answers. Names and student numbers have been removed, and questions have been paraphrased to ensure anonymity.

Sebastiaan Mathôt and Wouter Kruijne

Faculty of Behavioral and Social Sciences, University of Groningen, Netherlands

- <https://github.com/rug-gmw/heymans>

## Getting started

Import relevant libraries and specify model. Ideally, you set API keys through environment variables. You can also specify your API directly in the code below. Make sure that you do not accidentally make your API key publicly available though!

You can install Heymans and all dependencies from PyPi:

```
pip install heymans
```
"""
import json
from pathlib import Path
from sigmund import config as sigmund_config
from heymans import convert, quizzes, report

# Anthropic setings
# If available, the ANTHROPIC_API_KEY environment variable is used
if sigmund_config.anthropic_api_key is None:  
    sigmund_config.anthropic_api_key = 'your API key here (never share!)'
MODEL = 'claude-4-sonnet'

# OpenAI settings
# If available, the OPENAI_API_KEY environment variable is used
# if sigmund_config.openai_api_key is None:
#     sigmund_config.openai_api_key = 'your API key here (never share!)'
# MODEL = 'gpt-4o'

# Mistral settings
# If available, the MISTRAL_API_KEY environment variable is used
# if sigmund_config.mistral_api_key is None:
#     sigmund_config.mistral_api_key = 'your API key here (never share!)'
# MODEL = 'mistral-large'
print(f'Heymans will use {MODEL}')

"""
## Preparing the exam

### Writing the exam

The exam should be written in the Markdown format as used in `example/exam-questions.md`.

### Validating the exam

Once you have written the exam, you can validate it. This means that Heymans will inspect all questions and their answer keys, and provide suggestions for improvement. You'll find that Heymans typically has many suggestions, and you do not need to implement them all. Rather, use these suggestions as a starting point for your own careful evaluation.
"""
output = report.validate_exam('exam-questions.md', model=MODEL, 
                              dst='output/exam-validation.md')
print(output)

"""
### Uploading the exam to Brightspace

The exam should be converted to a CSV-like format that is used by Brightspace. You can import these questions by first creating a Brightspace quiz, and then using Add Existing -> Upload a File.
"""
convert.to_brightspace_exam('exam-questions.md', points_per_question=1,
                            dst='output/brightspace-questions.csv')

"""
## Grading the exam

### Score the attempts

Download the quiz results from Brightspace by going to Assessment -> Quizzes -> Click menu -next to your exam -> Grade -> Export to CSV. Save the results as `brightspace-results.csv`. This file is combined with the original questions to create a quiz-data object that contains all the information. This can then be graded, and written to file!

Important: Based on the quality checks below, you may find that the answer key needs to be updated, for example because the students provided correct answers that you did not consider beforehand. If so, then simply modify the answer key and regrade the exam from here.
"""
quiz_data = convert.merge_brightspace_attempts('exam-questions.md',
                                               'brightspace-results.csv')
# Scoring can take a long time!
quiz_data = report.score(quiz_data, model=MODEL,
                         dst='output/quiz-data.json')


"""
### Check for grading errors

To make sure that everything went smoothly, it is important to check for grading errors. If any errors occurred, the details of the errors can be found in the generated errors report (WARNING_ERRORS_OCCURRED.md). Based on this error report, you can then decide to score the failed attempts manually, or re-run the grading.

The most likely sources of grading errors are persistent connectivity issues between Heymans and the AI-model provider, or persistent errors in the responses of the AI model.
"""
errors = report.check_grading_errors(quiz_data,
                                     dst='output/WARNING_ERRORS_OCCURRED.md')
if errors is not None:
    print(errors)
else:
    print('No errors occurred during grading!')
    

"""
### Difficulty and discrimination of questions

Let's start with analyzing the difficulty and discrimination of the questions. This provides a mean score for each questions, and an RIR measure, which indicates how highly the score of a question correlates with the score on all other questions. Ideally, the mean score is about .7 and the RIR is a positive value of at least .2.
"""
dm = report.analyze_difficulty_and_discrimination(
    quiz_data, dst='output/difficulty-and-discrimination.csv',
    figure='output/difficulty-and-discrimination.png')
print(dm)

"""
### Qualitative error analysis

The qualitative error analysis provides suggestions for improving the answer keys based on a review of all incorrect student answers.
"""
output = report.analyze_qualitative_errors(
    quiz_data, model=MODEL, dst='output/qualitative-error-analysis.md')
print(output)

"""
### Save grades

Save the results!
"""
output = report.calculate_grades(quiz_data, dst='output/grades.csv',
                                 figure='output/grades.png')
print(output)


"""
### Individual feedback

Generate a markdown and PDF report for each student with complete feedback.
"""
report.generate_feedback(quiz_data, output_folder='feedback')
