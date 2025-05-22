import os
import base64

# SERVER
#
# The external server address, that is, the URL that users visit
server_url = os.environ.get('FLASK_SERVER_URL', 'http://127.0.0.1:5000')
# The port at which the flask server is running internally. This can be
# different from the server URL if the app is running behind a proxy that
# redirects
flask_port = int(os.environ.get('FLASK_PORT', 5000))
# The flask host arhument where all 0s means listen to all incoming addresses
flask_host = os.environ.get('FLASK_HOST', '0.0.0.0')
# The secret key is used for logging in. This should be a long and arbitrary
# string that is hard to guess. This should not be shared
flask_secret_key = os.environ.get('FLASK_SECRET_KEY', '0123456789ABCDEF')

encryption_salt = base64.urlsafe_b64decode(
    os.environ.get("ENCRYPTION_SALT", "ZGVmYXVsdF9zYWx0X2Zvcl90ZXN0aW5n")
)
# GOOGLE SSO OPTIONS:
google_login_enabled = True
google_client_id = os.environ.get("GOOGLE_CLIENT_ID", None)
google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", None)
google_discovery_url = (
    "https://accounts.google.com/.well-known/openid-configuration"
)
# Default model to use
default_model = os.environ.get('HEYMANS_DEFAULT_MODEL', 'gpt-4.1')

# DEV OPTIONS
#
# Use a dummy model during development
dummy_model = bool(int(os.environ.get('HEYMANS_DUMMY_MODEL', 0)))

# QUIZ GRADING
#
# The minimum number of characters that an answer should have
min_answer_length = 2
# The maximum duration in seconds that grading a single attempt should take
grading_task_timeout = 60
validation_task_timeout = 300


# DOCUMENTS
#
# The maximum chunk size in characters
document_max_chunk_size = 10000
