class ResumeProcessingError(Exception):
    """Base class for resume processing errors."""


class InvalidPDFError(ResumeProcessingError):
    """Raised when uploaded file content is not a valid PDF."""


class AIServiceTimeoutError(ResumeProcessingError):
    """Raised when AI provider takes too long to return."""


class AIServiceUnavailableError(ResumeProcessingError):
    """Raised when all configured AI providers fail."""


class AIResponseParseError(ResumeProcessingError):
    """Raised when AI response is not valid structured JSON."""
