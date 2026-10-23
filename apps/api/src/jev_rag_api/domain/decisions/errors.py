class DecisionError(Exception):
    code = "DECISION_ERROR"
    retryable = False

    def __init__(self, provider_request_id: str | None = None) -> None:
        self.provider_request_id = provider_request_id
        super().__init__(self.code)


class DecisionInvalidRequestError(DecisionError):
    code = "DECISION_INVALID_REQUEST"


class DecisionAuthenticationError(DecisionError):
    code = "DECISION_AUTHENTICATION"


class DecisionRateLimitedError(DecisionError):
    code = "DECISION_RATE_LIMITED"
    retryable = True


class DecisionUnavailableError(DecisionError):
    code = "DECISION_UNAVAILABLE"
    retryable = True


class DecisionTimeoutError(DecisionError):
    code = "DECISION_TIMEOUT"
    retryable = True


class DecisionInvalidResponseError(DecisionError):
    code = "DECISION_INVALID_RESPONSE"


class DecisionConfigurationError(DecisionError):
    code = "DECISION_CONFIGURATION"
