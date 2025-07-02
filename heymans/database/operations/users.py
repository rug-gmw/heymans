import logging
from ..models import db, User

logger = logging.getLogger('heymans')


def create_user_if_not_exists(username: str, user_id: int = None) -> int:
    """Create a user if it doesn't exist, or return the existing user_id.
    
    Parameters
    ----------
    username : str
        The username for the user
    user_id : int, optional
        Optional user_id. If provided, checks if a user with this 
        id exists. If not provided, always creates a new user.
    
    Returns
    -------
    int
        The user_id of the existing or newly created user
        
    Notes
    -----
    Behavior depends on whether user_id is provided:
    
    - If user_id is provided and exists: returns that user_id (no changes)
    - If user_id is provided but doesn't exist: creates user with that id
    - If user_id is not provided: always creates a new user
    """
    with db.session.begin():
        if user_id is not None:
            # Check if user with this id already exists
            existing_user = db.session.get(User, user_id)
            if existing_user:
                logger.info('User %s already exists with username %s', 
                           user_id, existing_user.username)
                return existing_user.user_id
            
            # Create new user with specified id
            user = User(user_id=user_id, username=username)
            db.session.add(user)
            db.session.flush()
            logger.info('Created user %s with username %s', user_id, username)
            return user.user_id
        else:
            # No user_id provided, always create new user
            user = User(username=username)
            db.session.add(user)
            db.session.flush()
            logger.info('Created new user with username %s, assigned id %s', 
                       username, user.user_id)
            return user.user_id