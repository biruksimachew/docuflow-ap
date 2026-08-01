class AuthenticationError(Exception):
    """A bearer token could not authenticate an application user."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
    ) -> None:
        super().__init__(
            message
        )

        self.code = code
        self.message = message
        self.status_code = 401


class AuthorizationError(Exception):
    """An authenticated user lacks an application permission."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
    ) -> None:
        super().__init__(
            message
        )

        self.code = code
        self.message = message
        self.status_code = 403