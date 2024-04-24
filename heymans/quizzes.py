from redis import Redis
import json
import logging
from .database import operations as ops

logger = logging.getLogger('heymans')
GRADING_IN_PROGRESS = 'grading_in_progress'
GRADING_ABORTED = 'grading_aborted'
GRADING_DONE = 'grading_done'
NEEDS_GRADING = 'needs_grading'
GRADING_TASK_TIMEOUT = 60
redis_client = Redis(decode_responses=True)


def quiz_grading_task(quiz, prompt, model):
    import time
    
    quiz_id = quiz['quiz_id']
    redis_key_status= f'quiz_grading_task_status:{quiz_id}'
    redis_client.set(redis_key_status, GRADING_IN_PROGRESS)
    redis_client.expire(redis_key_status, GRADING_TASK_TIMEOUT)
    redis_key_result = f'quiz_grading_task_result:{quiz_id}'
    attempts = []
    for question in quiz.get('questions', []):
        for attempt in question.get('attempts', []):
            print('grading attempt')
            attempt['feedback'] = 'dummy feedback'
            attempt['score'] = 1
            attempts.append(attempt)
            time.sleep(.5)
            redis_client.set(redis_key_result, json.dumps(attempts))
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
