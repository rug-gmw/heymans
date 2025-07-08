import os
from dotenv import load_dotenv
# Check if .env exists in the folder of this file, and if so load it, otherwise
# do nothing
if os.path.exists(os.path.join(os.path.dirname(__file__), '.env')):
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from heymans.server import create_app
from heymans import config

app = create_app()
if __name__ == '__main__':
    app.run(host=config.flask_host, port=config.flask_port)
