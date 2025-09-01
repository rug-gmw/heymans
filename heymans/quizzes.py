from redis import Redis
import json
import multiprocessing as mp
import logging
import time
from .database.operations import quizzes as ops
from . import prompts, report, json_schemas, config
from .chatbot_model import chatbot_model
from langchain.schema import SystemMessage, HumanMessage
from jsonschema import validate

logger = logging.getLogger('heymans')
redis_client = Redis(decode_responses=True)
ERROR_MARKER = 'ERROR:'
GRADING_IN_PROGRESS = 'grading_in_progress'
GRADING_ERROR = 'grading_error'
GRADING_NEEDS_COMMIT = 'grading_needs_commit'
GRADING_DONE = 'grading_done'
NEEDS_GRADING = 'needs_grading'
VALIDATION_IN_PROGRESS = 'validation_in_progress'
VALIDATION_ABORTED = 'validation_aborted'
VALIDATION_DONE = 'validation_done'
NEEDS_VALIDATION = 'needs_validation'
STATE_EMPTY = 'empty'
STATE_HAS_QUESTIONS = 'has_questions'
STATE_HAS_ATTEMPTS = 'has_attempts'
STATE_HAS_SCORES = 'has_scores'


def state(quiz_info: dict) -> str:
    """Determine the state of a quiz.

    Return values:
        - STATE_EMPTY        : quiz has no questions
        - STATE_HAS_QUESTIONS: quiz has questions but no attempts
        - STATE_HAS_ATTEMPTS : at least one attempt exists, but ≥1 attempt
                               is missing a score
        - STATE_HAS_SCORES   : at least one attempt exists and *all* attempts
                               have scores (None / missing scores count as
                               “not scored”)
    """
    questions = quiz_info.get("questions", [])

    # No questions at all ➜ empty
    if not questions:
        return STATE_EMPTY

    found_attempt = False
    all_attempts_scored = True

    for question in questions:
        attempts = question.get("attempts", [])

        if attempts:
            found_attempt = True

            for attempt in attempts:
                # Treat a missing or None score as “not scored”
                if attempt.get("score") is None:
                    all_attempts_scored = False

    # Questions but no attempts ➜ has_questions
    if not found_attempt:
        return STATE_HAS_QUESTIONS

    # Attempts exist, but at least one lacks a score ➜ has_attempts
    if not all_attempts_scored:
        return STATE_HAS_ATTEMPTS

    # All attempts have scores ➜ has_scores
    return STATE_HAS_SCORES
    
    
def clear_redis(quiz_id: int):
    """Clears all redis info related to a quiz"""
    redis_client.delete(f'quiz_grading_task_status:{quiz_id}')
    redis_client.delete(f'quiz_grading_task_result:{quiz_id}')
    redis_client.delete(f'quiz_validation_task_status:{quiz_id}')
    redis_client.delete(f'quiz_validation_task_result:{quiz_id}')


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
                  retries: int = None) -> tuple:
    """Grades a single attempt to a question using a language model
    
    Parameters
    ----------
    question : str
        The question that was asked
    answer_key : str
        The answer key for the question
    answer : str
        The answer that was given
    model : str
        The model to use for grading
    retries : int
        The number of retries to use for the model
    
    Returns
    -------
    tuple
        A tuple containing the score and feedback. The feedback consists of a
        list of dictionaries, each containing a boolean 'pass' and a string
        'motivation'.
    """
    if len(answer.strip()) < config.min_answer_length:
        return 0, [{'pass': False, 'motivation': 'No answer provided'}]
    if retries is None:
        retries = config.grading_max_retries
    client = chatbot_model(
        model,
        dummy_reply=json.dumps([{'pass': True, 'motivation': 'Dummy model'}])
    )
    # We determine the response prompt dynamically so that it takes into 
    # account the number of points in the answer key
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
                f'grading failed too many times ({e}), giving up ...')
            return 0, [{'pass': False,
                        'motivation': f'{ERROR_MARKER} {e}'}]
        logger.warning(f'grading failed ({e}), retrying ...')
        if not isinstance(e, json.JSONDecodeError):
            delay = 1 + config.grading_max_retries - retries
            logger.warning(f'Waiting for {delay} s ...')
            time.sleep(delay)
        return grade_attempt(question, answer_key, answer, model,
                             retries=retries - 1)
    score = sum(point['pass'] for point in response_list)
    return score, response_list
    
    
def _grade_attempt_worker(question, attempt, model):
    """A worker task that can be called by Pool.starmap."""
    if attempt.get('score', None) is not None:
        logger.info('attempt already graded')
        return attempt
    score, feedback = grade_attempt(
        question['text'],
        question['answer_key'],
        attempt['answer'],
        model)
    attempt['feedback'] = feedback
    attempt['score'] = score
    return attempt
    

def quiz_grading_task(quiz: dict, model: str):
    """Grades all attempts in a quiz. This function is mainly intended to be
    called as a background process and then polled with 
    poll_quiz_grading_task. But for development purposes the function can
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
    n_total = 0
    for question in quiz.get('questions', []):
        n_total += len(question.get('attempts', []))
    logger.info(f'Starting grading {n_total} attempts')
    n_done = 0    
    # Process each question separately
    for question_idx, question in enumerate(quiz.get('questions', [])):
        attempts_to_grade = question.get('attempts', [])        
        if not attempts_to_grade:
            continue            
        # Prepare arguments for this question's attempts
        starmap_args = [(question, attempt, model) for attempt in attempts_to_grade]
        n_done += len(starmap_args)        
        # Grade all attempts for this question in parallel
        with mp.Pool(config.grading_task_max_concurrent) as pool:
            graded_attempts = pool.starmap(_grade_attempt_worker, starmap_args)        
        # Replace the attempts with the graded versions
        quiz['questions'][question_idx]['attempts'][:len(graded_attempts)] = graded_attempts    
        logger.info(f'Finished grading {n_done} / {n_total} attempts')    
        # Store the intermediate result in Redis
        redis_client.set(redis_key_result, json.dumps(quiz))
    # A second round of grading without multiprocessing, to redo any attempts
    # that for some reason weren't graded before.
    errors_occurred = 0
    for question in quiz.get('questions', []):
        for attempt in question.get('attempts', []):
            motivation = attempt['feedback'][0]['motivation']
            if motivation and not motivation.startswith(ERROR_MARKER):
                continue
            logger.warning('grading attempt again ...')
            _grade_attempt_worker(question, attempt, model)
            motivation = attempt['feedback'][0]['motivation']
            if not motivation or motivation.startswith(ERROR_MARKER):
                errors_occurred += 1
            # Store the intermediate result in Redis
            redis_client.set(redis_key_result, json.dumps(quiz))
    if errors_occurred:
        logger.error(f'{errors_occurred} attempts could not be graded')
        redis_client.set(redis_key_status, GRADING_ERROR)
    else:
        logger.info('all attempts were graded successfully')
        quiz['qualitative_error_analysis'] = \
            report.analyze_qualitative_errors(quiz, model)
        redis_client.set(redis_key_status, GRADING_NEEDS_COMMIT)
    redis_client.set(redis_key_result, json.dumps(quiz))
    
    
def poll_quiz_grading_task(quiz_id: int, user_id: int) -> str:
    """Checks if a grading task is completed, and if so commits the results to
    the database. In addition, returns whether a grading task is currently
    running.
    """
    redis_key_status = f'quiz_grading_task_status:{quiz_id}'
    redis_key_result = f'quiz_grading_task_result:{quiz_id}'
    status = redis_client.get(redis_key_status)
    # Task doesn't exist yet. This usually means that grading has never started
    # in which case we should return GRADING_DONE. However, it may also mean 
    # that the redis server was cleared, in which case we query the database to
    # see if the quiz was graded and updated redis accordingly.
    if status is None:        
        quiz = ops.get_quiz(quiz_id, user_id)
        if state(quiz) == STATE_HAS_SCORES:
            logger.info(
                f'grading done based on database state for quiz {quiz_id}')
            redis_client.set(redis_key_status, GRADING_DONE)
            return GRADING_DONE
        logger.info(f'needs grading based on database state for quiz {quiz_id}')
        redis_client.set(redis_key_status, NEEDS_GRADING)
        return NEEDS_GRADING
    # The task exists and is still running
    if status == GRADING_IN_PROGRESS:
        logger.info(f'no grades to commit for quiz {quiz_id}')
    elif status == GRADING_NEEDS_COMMIT:
        # The task exists and is done, but the grades still need to be 
        # committed. Once the grades are committed, the redis state is changed
        # to grading done.
        grading_results = redis_client.get(redis_key_result)
        if grading_results is not None:
            # There are new grading results, which need to be committed
            quiz_data = json.loads(str(grading_results))
            ops.update_attempts(quiz_id, quiz_data, user_id)
            logger.info(f'grades committed for quiz {quiz_id}')
            redis_client.delete(redis_key_result)
        else:
            # There are no new grading results, most likely because everything 
            # was already graded.
            logger.info(f'no grades to commit for quiz {quiz_id}')
        redis_client.set(redis_key_status, GRADING_DONE)
        status = GRADING_DONE
    return status


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
        ops.update_quiz(quiz_id, quiz_info, user_id)
        logger.info(f'validation committed for quiz {quiz_id}')
        redis_client.delete(redis_key_result)
    else:
        logger.info(f'no new validation results to commit for quiz {quiz_id}')

    # Clean up
    redis_client.delete(redis_key_status)

    return False