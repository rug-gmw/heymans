# Heymans AI tutor

Copyright 2024-2026 Sebastiaan Mathôt (@smathot), Wouter Kruijne (@wkruijne), University of Groningen

Heymans AI tutor is a Python library and web app for LLM-based teaching tools. The initial focus will be on automated grading of open exams and interactive quizzes.

This software is in early stages of development and not ready for production.


## Dependencies

For Python dependencies, see `pyproject.toml`. Python 3.10 or later is required. In addition to these, a local `redis` server needs to run for persistent data between sessions. `pandoc` needs to be installed for generating invidual feedback reports.


## Configuration

Copy `.env.example` to `.env` and modify it. See `heymans/config.py` for more information about the various configuration options.


## Using as Python library

See `example/heymans-brightspace-example.py` for an example of how to grade an open-ended exam. This example assumes that you're using the Brightspace learning environment. The example folder also contains example output that is generated during grading.


## Running as web server (development)

Download the source code, and in the folder of the source code execute the following:

```
pip install .               # install dependencies
python app.py               # start the app
```

Next, access the app (by default) through:

```
http://127.0.0.1:5000/app/quiz
```

## Testing

The basic Heymans functionality is tested with the 'cheap' testcases, which can be run like so:

```
pytest tests/cheap
```

Brightspace connectivity requires an API token, which needs to be retrieved first. For this, you need access to a Brightspace test environment with credentials as specified in `.env`. To get a token, first start a simple app to log into Brightspace and save a temporary token to disk:

```
python bs_get_token.py
```

In a browser, navigate to https://127.0.0.1:5000 (ignore the security warning) and log into Brightspace. The app will close automatically. Now run the Brightspace testcases:

```
pytest tests/brightspace
```


## License

Heymans is distributed under the terms of the GNU General Public License 3. The full license should be included in the file `COPYING`, or can be obtained from:

- <http://www.gnu.org/licenses/gpl.txt>
