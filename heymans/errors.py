class HeymansError(ValueError):
    """Base class for user-facing Heymans errors."""

    code = 'heymans_error'

    def __init__(self, message, **details):
        super().__init__(message)
        self.message = message
        self.details = details

    def to_dict(self):
        return {
            'error': self.message,
            'code': self.code,
            **self.details,
        }


class QuizFileError(HeymansError):
    """Raised when an uploaded quiz file cannot be parsed."""

    code = 'quiz_file_error'

    def __init__(self, message, question_name=None, context=None, hint=None):
        super().__init__(
            message,
            question_name=question_name,
            context=context,
            hint=hint,
        )


class AttemptsFileError(HeymansError):
    """Raised when an uploaded attempts file cannot be merged with quiz questions."""

    code = 'attempts_file_error'

    def __init__(self, message, context=None, hint=None):
        super().__init__(
            message,
            context=context,
            hint=hint,
        )


class DocumentFileError(HeymansError):
    """Raised when an uploaded document cannot be processed."""

    code = 'document_file_error'

    def __init__(self, message, reason, **details):
        super().__init__(message, reason=reason, **details)
