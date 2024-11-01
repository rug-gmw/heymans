# Heymans AI tutor

Copyright 2024 University of Groningen

A Python library and web app for LLM-based teaching tools. The initial focus will be on automated grading of open exams and interactive quizzes.

This software is in early stages of development and not ready for production.


## Dependencies

For Python dependencies, see `pyproject.toml`. In addition to these, a local `redis` server needs to run for persistent data between sessions.


## Running (development)

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
