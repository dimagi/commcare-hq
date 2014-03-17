from django.conf import settings

# this isn't OR specific, but we like it to be included
OPENROSA_ACCEPT_LANGUAGE = "HTTP_ACCEPT_LANGUAGE"
OPENROSA_VERSION_HEADER = "HTTP_X_OPENROSA_VERSION"
OPENROSA_DATE_HEADER = "HTTP_DATE"
OPENROSA_HEADERS = [OPENROSA_VERSION_HEADER, OPENROSA_DATE_HEADER, OPENROSA_ACCEPT_LANGUAGE]


class OpenRosaMiddleware(object):
    """
    Middleware to support OpenRosa request/response standards compliance 
    https://bitbucket.org/javarosa/javarosa/wiki/OpenRosaRequest
    """
    
    def __init__(self):        
        pass

    def process_request(self, request):
        # if there's a date header specified add that to the request 
        # as a first class property
        or_headers = {}
        for header in OPENROSA_HEADERS:
            if header in request.META:
                or_headers[header] = request.META[header]
        request.openrosa_headers = or_headers

    def process_response(self, request, response):
        response[OPENROSA_VERSION_HEADER] = settings.OPENROSA_VERSION
        return response
