from ._replies import no_content, not_found, success, forbidden, \
    invalid_json, missing_file, error
from ._quizzes import quizzes_api_blueprint
from ._app import app_blueprint
from ._documents import documents_api_blueprint
from ._user import user_api_blueprint
