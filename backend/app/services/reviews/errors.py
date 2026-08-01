class ReviewCaseNotFoundError(Exception):
    """The requested review case does not exist."""


class ReviewCaseConflictError(Exception):
    """The requested review transition conflicts with current state."""


class ReviewCaseAuthorizationError(Exception):
    """The current user cannot perform the requested transition."""