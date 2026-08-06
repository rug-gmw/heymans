# Frontend smoke quiz with invalid answer-key dashes

## Broken question

This question uses lookalike dash characters in the answer key, so the frontend
should show the server's markdown parse error instead of silently accepting it.

– This line starts with an en dash, not a regular hyphen
– This line also starts with an en dash
