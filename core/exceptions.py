class AppError(Exception):
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None, status_code: int | None = None):
        if detail:
            self.detail = detail
        if status_code:
            self.status_code = status_code
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = 404
    error_code = "NOT_FOUND"


class ValidationError(AppError):
    status_code = 400
    error_code = "VALIDATION_ERROR"


class AuthError(AppError):
    status_code = 401
    error_code = "AUTH_ERROR"


class RateLimitError(AppError):
    status_code = 429
    error_code = "RATE_LIMITED"


class DatabaseError(AppError):
    status_code = 500
    error_code = "DATABASE_ERROR"


class LLMError(AppError):
    status_code = 502
    error_code = "LLM_ERROR"


class QueryError(AppError):
    status_code = 400
    error_code = "QUERY_ERROR"
