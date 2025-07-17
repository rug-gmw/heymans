# Heymans AI tutor

Copyright 2024-2025 University of Groningen, developed by @smathot and @wkruijne

Heymans AI tutor is a Python library and web app for LLM-based teaching tools. The initial focus will be on automated grading of open exams and interactive quizzes.

This software is in early stages of development and not ready for production.


## Dependencies

For Python dependencies, see `pyproject.toml`. Python 3.10 or later is required. In addition to these, a local `redis` server needs to run for persistent data between sessions. `pandoc` needs to be installed for generating invidual feedback reports.

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


## License

Heymans is distributed under the terms of the GNU General Public License 3. The full license should be included in the file `COPYING`, or can be obtained from:

- <http://www.gnu.org/licenses/gpl.txt>
