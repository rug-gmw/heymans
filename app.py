from dotenv import load_dotenv
load_dotenv()
from heymans.server import create_app
from heymans import config

app = create_app()
if __name__ == '__main__':
    # When running locally during development, we need an adhoc ssl context to
    # allow the oauth logins to work.
    if 'localhost' in config.server_url or '127.0.0.1' in config.server_url:
        kwargs = {'ssl_context': 'adhoc'}
    else:
        kwargs = {}
    app.run(host=config.flask_host, port=config.flask_port, **kwargs)
