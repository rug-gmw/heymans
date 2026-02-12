from redis import Redis


redis_client = Redis(decode_responses=True)


def clear_quiz_status(quiz_id: int):
    """Clears all redis info related to a quiz"""
    redis_client.delete(f'quiz_grading_task_status:{quiz_id}')
    redis_client.delete(f'quiz_grading_task_result:{quiz_id}')
    redis_client.delete(f'quiz_validation_task_status:{quiz_id}')
    redis_client.delete(f'quiz_validation_task_result:{quiz_id}')
    
    
def flush():
    Redis().flushdb()
