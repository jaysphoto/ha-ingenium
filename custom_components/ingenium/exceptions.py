"""Ingenium exceptions."""


class IngeniumException(Exception):
    """Base class for exceptions."""


class IngeniumHttpNetworkError(IngeniumException):
    """Error to indicate a network error occurred."""


class IngeniumHttpClientError(IngeniumException):
    """Error to indicate client request error occurred."""


class IngeniumHttpServerError(IngeniumException):
    """Error to indicate server response error occurred."""


class IngeniumNotSupportedError(IngeniumException):
    """Error to indicate device is not supported."""
