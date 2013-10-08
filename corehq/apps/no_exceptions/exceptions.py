"""
This is a list of exceptions which will raise an appropriate http error
response.
Http404 is not overridden, but is included here for convenience.
"""
from django.http import Http404


class BaseHttpException(Exception):
    status = None
    error_class = "ERROR"
    meaning = ''
    message = ''

    def __init__(self, message=None):
        if message is not None:
            self.message = message

    def render(self):
        status = self.status or ''
        return "HTTP {0} - {1} - {2}: {3}".format(
                status, self.error_class, self.meaning, self.message)


class HttpException(BaseHttpException):
    """
    Use this to make your own exception on the fly.

    Example:
    raise x.HttpException(
        status=418,
        message="I can't help you, I'm a teapot"
    )
    """

    def __init__(self, status, message=None):
        self.status = status
        if 400 <= status < 500:
            self.error_class = "CLIENT ERROR"
        self.meaning = REASON_PHRASES[status]
        if message is not None:
            self.message = message


################
# Client Error #
################

class Http400(BaseHttpException):
    status = 400
    error_class = "CLIENT ERROR"
    meaning = "BAD REQUEST"


class Http401(Http400):
    "Client needs to authenticate"
    status = 401
    meaning = "UNAUTHORIZED" 
    message = "You need to log-in"


class Http403(Http400):
    "Client is authenticated, but needs permission"
    status = 403
    meaning = "FORBIDDEN"
    message = "You do not have permission to complete that request"


class Http418(Http400):
    status = 418
    meaning = "I'M A TEAPOT"


# Copied from django.http.response (not available in 1.3)
REASON_PHRASES = {
    100: 'CONTINUE',
    101: 'SWITCHING PROTOCOLS',
    102: 'PROCESSING',
    200: 'OK',
    201: 'CREATED',
    202: 'ACCEPTED',
    203: 'NON-AUTHORITATIVE INFORMATION',
    204: 'NO CONTENT',
    205: 'RESET CONTENT',
    206: 'PARTIAL CONTENT',
    207: 'MULTI-STATUS',
    208: 'ALREADY REPORTED',
    226: 'IM USED',
    300: 'MULTIPLE CHOICES',
    301: 'MOVED PERMANENTLY',
    302: 'FOUND',
    303: 'SEE OTHER',
    304: 'NOT MODIFIED',
    305: 'USE PROXY',
    306: 'RESERVED',
    307: 'TEMPORARY REDIRECT',
    400: 'BAD REQUEST',
    401: 'UNAUTHORIZED',
    402: 'PAYMENT REQUIRED',
    403: 'FORBIDDEN',
    404: 'NOT FOUND',
    405: 'METHOD NOT ALLOWED',
    406: 'NOT ACCEPTABLE',
    407: 'PROXY AUTHENTICATION REQUIRED',
    408: 'REQUEST TIMEOUT',
    409: 'CONFLICT',
    410: 'GONE',
    411: 'LENGTH REQUIRED',
    412: 'PRECONDITION FAILED',
    413: 'REQUEST ENTITY TOO LARGE',
    414: 'REQUEST-URI TOO LONG',
    415: 'UNSUPPORTED MEDIA TYPE',
    416: 'REQUESTED RANGE NOT SATISFIABLE',
    417: 'EXPECTATION FAILED',
    418: "I'M A TEAPOT",
    422: 'UNPROCESSABLE ENTITY',
    423: 'LOCKED',
    424: 'FAILED DEPENDENCY',
    426: 'UPGRADE REQUIRED',
    428: 'PRECONDITION REQUIRED',
    429: 'TOO MANY REQUESTS',
    431: 'REQUEST HEADER FIELDS TOO LARGE',
    500: 'INTERNAL SERVER ERROR',
    501: 'NOT IMPLEMENTED',
    502: 'BAD GATEWAY',
    503: 'SERVICE UNAVAILABLE',
    504: 'GATEWAY TIMEOUT',
    505: 'HTTP VERSION NOT SUPPORTED',
    506: 'VARIANT ALSO NEGOTIATES',
    507: 'INSUFFICIENT STORAGE',
    508: 'LOOP DETECTED',
    510: 'NOT EXTENDED',
    511: 'NETWORK AUTHENTICATION REQUIRED',
}


