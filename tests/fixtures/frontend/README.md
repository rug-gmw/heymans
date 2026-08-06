# Frontend Fixtures

This directory contains fixtures for user-facing frontend checks. Organize files
by the page or workflow where a user encounters them, not by parser or backend
module.

These fixtures are intended for two uses:

- manual smoke checks while developing the frontend
- future browser-level tests, for example with Playwright

Each page folder should contain a `cases.yaml` file that documents:

- the route to open
- the action to perform
- the fixture file to use, if any
- the expected visible result

Use short, regular fields so these cases remain useful to a person reading them
in a terminal and can later be loaded by browser-level tests.

Keep parser-only fixtures in the existing pytest areas unless they are also
useful for testing a frontend workflow.

## Folders

- `app_quiz/`: `/app/quiz`
- `app_kb/`: `/app/kb`
- `app_iquiz/`: `/app/iquiz`
- `public_interactive_quizzes_start/`: `/public/interactive_quizzes/start/<id>`
