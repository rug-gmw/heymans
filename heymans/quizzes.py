from redis import Redis
import json
import logging
from .database.operations import quizzes as ops
from . import prompts, report, json_schemas, config
from sigmund.model import model as chatbot_model
from langchain.schema import SystemMessage, HumanMessage
from jsonschema import validate

logger = logging.getLogger('heymans')
GRADING_IN_PROGRESS = 'grading_in_progress'
GRADING_ABORTED = 'grading_aborted'
GRADING_DONE = 'grading_done'
NEEDS_GRADING = 'needs_grading'
VALIDATION_IN_PROGRESS = 'validation_in_progress'
VALIDATION_ABORTED = 'validation_aborted'
VALIDATION_DONE = 'validation_done'
NEEDS_VALIDATION = 'needs_validation'
redis_client = Redis(decode_responses=True)


def answer_key_length(answer_key: [list, str]) -> int:
    """Determines the number of motivated points that is expected based on an
    answer key. Normally, this is equal to the number of elements from the 
    answer key, but a single element can optionally specify that more motivated
    points are expected, like so: "3:answer key text"
    """
    n_answer_key_points = 0
    for answer_key_point in answer_key:
        if len(answer_key_point) >= 2 and answer_key_point[0].isdigit() \
                and answer_key_point[1] == ':':
            n_answer_key_points += int(answer_key_point[0])
        else:
            n_answer_key_points += 1
    return n_answer_key_points


def grade_attempt(question: str, answer_key: str, answer: str, model: str,
                  retries: int = 3) -> tuple:
    if len(answer.strip()) < config.min_answer_length:
        return 0, [{'pass': False, 'motivation': 'No answer provided'}]
    if config.dummy_model:
        return 1, [{'pass': True, 'motivation': 'Dummy model'}]
    client = chatbot_model(None, model=model)
    formatted_answer_key = '- ' + '\n- '.join(answer_key)
    n_answer_key_points = answer_key_length(answer_key)
    formatted_reply_format = []
    for i in range(n_answer_key_points):
        formatted_reply_format.append({
            'pass': True,
            'motivation': f'Brief motivation for why point {i + 1} from the answer key is correct or not.'})
    formatted_reply_format = json.dumps(formatted_reply_format, indent=True)
    prompt = prompts.QUIZ_GRADING_PROMPT.render(
        question=question, answer_key=formatted_answer_key,
        reply_format=formatted_reply_format,
        n_answer_key_points=n_answer_key_points)
    messages = [SystemMessage(content=prompt), HumanMessage(content=answer)]
    try:
        response = client.predict(messages)
        print(response, type(response))
        # Turn JSON code blocks into regular JSON
        response = response.replace('```\n', '')
        response = response.replace('```json\n', '')
        response = response.replace('```javascript\n', '')
        response = response.replace('```js\n', '')
        response = response.replace('\n```', '')
        response_list = json.loads(response)
        # Handle edge case where the answer key consists of only a single point
        # which the model sometimes forgets to put in a list
        if isinstance(response_list, dict):
            response_list = [response_list]
        validate(instance=response_list, schema=json_schemas.GRADING_RESPONSE)
        if len(response_list) != n_answer_key_points:
            raise ValueError('response length does not match answer key')
    except Exception as e:
        if retries == 0:
            logger.error(
                f'failed to parse grading response ({e}), giving up ...')
            return 0, [{'pass': False,
                        'motivation': 'ERROR: Failed to grade attempt'}]
        logger.warning(f'failed to parse grading response ({e}), retrying ...')
        return grade_attempt(question, answer_key, answer, model,
                             retries=retries - 1)
    score = sum(point['pass'] for point in response_list)
    return score, response_list
    

def quiz_grading_task(quiz: dict, model: str):
    """Grades all attempts in a quiz. This function is mainly intended to be
    called as a background process and then polled with 
    quiz_grading_task_running. But for development purposes the function can
    also be called directly.
    
    Parameters
    ----------
    quiz: dict
        The quiz information. This is modified in place.
    model: str
        The model specification, for example mistral-large
    """
    quiz_id = quiz['quiz_id']
    redis_key_status = f'quiz_grading_task_status:{quiz_id}'
    redis_client.set(redis_key_status, GRADING_IN_PROGRESS)
    redis_client.expire(redis_key_status, config.grading_task_timeout)
    redis_key_result = f'quiz_grading_task_result:{quiz_id}'
    n_total = len([attempt for question in quiz.get('questions', [])
                   for attempt in question.get('attempts', [])])
    attempts = []
    i = 0
    for question in quiz.get('questions', []):
        for attempt in question.get('attempts', []):
            if attempt.get('score', None) is not None:
                logger.info(f'graded {i} of {n_total} attempts already graded')
                i += 1
                continue
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
    
    
def quiz_grading_task_running(quiz_id: int, user_id: int) -> bool:
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
    # The task exists and is done
    grading_results = redis_client.get(redis_key_result)
    if grading_results is not None:
        # There are new grading results, which need to be committed
        attempts = json.loads(str(grading_results))
        ops.update_attempts(attempts, user_id)
        logger.info(f'grades committed for quiz {quiz_id}')
        redis_client.delete(redis_key_result)
    else:
        # There are no new grading results, most likely because everything was
        # already graded
        logger.info(f'no grades to commit for quiz {quiz_id}')
    redis_client.delete(redis_key_status)
    return False


def state(quiz_id: int, user_id: int) -> int:
    """Gets the state of a quiz, which is:
    
    0 - If there is no data
    1 - If there are questions, but no attempts
    2 - If there are ungraded attempts
    3 - If there are graded attempts
    """
    return 0


def quiz_validation_task(quiz_info: dict, model: str) -> None:
    """
    Runs an exam validation in the background by calling `report.validate_exam`
    and stores both the status and result in Redis so they can be polled later.

    Parameters
    ----------
    quiz_info : dict
        Quiz information. The dict is modified in‑place; a key "validation"
        will be added/updated with the validation result.
    model : str
        Model name to use for validation.
    """
    quiz_id = quiz_info['quiz_id']
    redis_key_status = f'quiz_validation_task_status:{quiz_id}'
    redis_key_result = f'quiz_validation_task_result:{quiz_id}'

    # Mark task as running
    redis_client.set(redis_key_status, VALIDATION_IN_PROGRESS)
    redis_client.expire(redis_key_status, config.validation_task_timeout)

    # --- Perform the (potentially expensive) validation --------------------
    logger.info(f'validation started for quiz {quiz_id}')
    validation_result = report.validate_exam(quiz_info, model)
    logger.info(f'validation finished for quiz {quiz_id}')
    quiz_info['validation'] = validation_result

    # Persist intermediate / final result for the polling helper
    redis_client.set(redis_key_result, json.dumps(quiz_info))

    # Mark task as completed
    redis_client.set(redis_key_status, VALIDATION_DONE)

    logger.info(f'validation finished for quiz {quiz_id}')


def quiz_validation_task_running(quiz_id: int, user_id: int) -> bool:
    """
    Polls whether a validation task is still running. If it is done, commits
    the result to the database and clears the Redis keys.

    Returns
    -------
    bool
        True  -> task exists and is still running
        False -> task does not exist OR it just finished and results were
                 committed successfully
    """
    redis_key_status = f'quiz_validation_task_status:{quiz_id}'
    redis_key_result = f'quiz_validation_task_result:{quiz_id}'

    status = redis_client.get(redis_key_status)

    # No task found
    if status is None:
        return False

    # Task is still running
    if status != VALIDATION_DONE:
        logger.info(f'validation still in progress for quiz {quiz_id}')
        return True

    # Task finished -> fetch & commit result
    quiz_info = redis_client.get(redis_key_result)
    if quiz_info is not None:
        quiz_info = json.loads(str(quiz_info))
        print(quiz_info)
        ops.update_quiz(quiz_id, quiz_info, user_id)
        logger.info(f'validation committed for quiz {quiz_id}')
        redis_client.delete(redis_key_result)
    else:
        logger.info(f'no new validation results to commit for quiz {quiz_id}')

    # Clean up
    redis_client.delete(redis_key_status)

    return False