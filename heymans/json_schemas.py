QUIZ = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["name", "questions"],
  "properties": {
    "quiz_id": {
      "type": "number"
    },
    "name": {
      "type": "string"
    },
    "questions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["text", "answer_key", "attempts"],
        "properties": {
          "question_id": {
            "type": "number"
          },
          "text": {
            "type": "string"
          },
          "answer_key": {
            "type": "string"
          },
          "attempts": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["username", "answer"],
              "properties": {
                "attempt_id": {
                  "type": "number"
                },
                "username": {
                  "type": "string",
                  "pattern": "^s[0-9]{8}$"
                },
                "answer": {
                  "type": "string"
                },
                "score": {
                  "type": ["number", "null"],
                  "minimum": 0
                },
                "feedback": {
                  "type": ["string", "null"]
                }
              }
            }
          }
        }
      },
      "minItems": 0
    }
  }
}

GRADING_START = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["quiz_id", "model"],
  "properties": {
    "quiz_id": {
      "type": "integer"
    },
    "model": {
      "type": "string"
    }
  }
}
