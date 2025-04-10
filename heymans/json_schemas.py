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
          "name": {
            "type": "string"
          },
          "text": {
            "type": "string"
          },
          "answer_key": {
            "type": "array",
            "items": {
              "type": "string"  
            }
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
                },
                "answer": {
                  "type": "string"
                },
                "score": {
                  "type": ["number", "null"],
                  "minimum": 0
                },
                "feedback": {
                  "type": ["array", "null"],
                  "items" : {
                    "type": "object",
                    "required": ["pass", "motivation"],
                    "properties": {
                      "pass": {
                        "type": "boolean",
                      },
                      "motivation": {
                        "type": "string",
                      }
                    }
                  }
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

GRADING_RESPONSE = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "pass": {
        "type": "boolean"
      },
      "motivation": {
        "type": "string"
      }
    },
    "required": [
      "pass",
      "motivation"
    ]
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

DOCUMENT = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "description": "Schema for file upload payload.",
  "type": "object",
  "properties": {
    "public": {
      "type": "boolean",
      "description": "Flag indicating whether the file should be publicly accessible"
    },
  },
  "required": ["public"]
}

DOCUMENT_UPDATE = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "description": "Schema for file upload payload.",
  "type": "object",
  "properties": {
    "document_id": {
      "type": "integer"
    },
    "public": {
      "type": "boolean",
      "description": "Flag indicating whether the file should be publicly accessible"
    },
  },
  "required": ["document_id", "public"]
}
