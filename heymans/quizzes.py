from redis import Redis
import json
import logging
from .database.operations import quizzes as ops
from . import prompts
from . import json_schemas
from jinja2 import Template
from sigmund.model import model as chatbot_model
from langchain.schema import SystemMessage, HumanMessage
from jsonschema import validate
from jsonschema.exceptions import ValidationError

logger = logging.getLogger('heymans')
GRADING_IN_PROGRESS = 'grading_in_progress'
GRADING_ABORTED = 'grading_aborted'
GRADING_DONE = 'grading_done'
NEEDS_GRADING = 'needs_grading'
GRADING_TASK_TIMEOUT = 60
redis_client = Redis(decode_responses=True)


def grade_attempt(question: str, answer_key: str, answer: str, model: str,
                  retries: int = 3) -> tuple:
    if isinstance(answer_key, str):
        answer_key = [point.strip(' \t-')
                      for point in answer_key.split('\n-')]
    client = chatbot_model(None, model=model)
    prompt = Template(prompts.QUIZ_GRADING_PROMPT).render(
        question=question, answer_key=json.dumps(answer_key),
        schema=json.dumps(json_schemas.GRADING_RESPONSE, indent='  '))
    messages = [SystemMessage(content=prompt), HumanMessage(content=answer)]
    try:
        response = client.predict(messages)
        response_list = json.loads(response)
        validate(instance=response_list, schema=json_schemas.GRADING_RESPONSE)
        if len(response_list) != len(answer_key):
            raise ValueError('response length does not match answer key')
    except Exception as e:
        if retries == 0:
            return 0, 'Failed to grade attempt'
        logger.warning(f'failed to parse grading response ({e}), retrying ...')
        return grade_attempt(question, answer_key, answer, model,
                             retries=retries - 1)
    score = sum(point['pass'] for point in response_list)
    return score, response
    

def quiz_grading_task(quiz: dict, model: str):
    """Grades all attempts in a quiz. This function is mainly intended to be
    called as a background process and then polled with 
    quiz_grading_task_running. But for development purposes the function can
    also be called directly.
    
    Parameters
    ----------
    quiz: dict
        The quiz information. This is modified in place.
    mode: str
        The model specification, for example mistral-large
    """
    quiz_id = quiz['quiz_id']
    redis_key_status = f'quiz_grading_task_status:{quiz_id}'
    redis_client.set(redis_key_status, GRADING_IN_PROGRESS)
    redis_client.expire(redis_key_status, GRADING_TASK_TIMEOUT)
    redis_key_result = f'quiz_grading_task_result:{quiz_id}'
    n_total = len([attempt for question in quiz.get('questions', [])
                   for attempt in question.get('attempts', [])])
    attempts = []
    i = 0
    for question in quiz.get('questions', []):
        for attempt in question.get('attempts', []):
            score, feedback = grade_attempt(
                question['text'],
                question['answer_key'],
                attempt['answer'],
                model)
            attempt['feedback'] = feedback
            attempt['score'] = score
            attempts.append(attempt)
            redis_client.set(redis_key_result, json.dumps(attempts))
            i += 1
            logger.info(f'graded {i} of {n_total} attempts')
    redis_client.set(redis_key_status, GRADING_DONE)  # reset expiration
    print('done grading')
    
    
def quiz_grading_task_running(quiz_id: int) -> bool:
    """Checks if a grading task is completed, and if so commits the results to
    the database. In addition, returns whether a grading task is currently
    running.
    """
    redis_key_status = f'quiz_grading_task_status:{quiz_id}'
    redis_key_result = f'quiz_grading_task_result:{quiz_id}'
    status = redis_client.get(redis_key_status)
    # The task doesn't exist
    if status is None:
        return False
    # The task exists and is still running
    if status != GRADING_DONE:
        logger.info(f'no grades to commit for quiz {quiz_id}')
        return True
    # The task exists but is done, in which case it needs to committed and
    # removed
    attempts = json.loads(str(redis_client.get(redis_key_result)))
    ops.update_attempts(attempts)
    logger.info(f'grades committed for quiz {quiz_id}')
    redis_client.delete(redis_key_status)
    redis_client.delete(redis_key_result)
    return False
