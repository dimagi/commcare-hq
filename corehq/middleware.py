import logging
import os
import datetime
from django.conf import settings

try:
    import psutil
except ImportError:
    psutil = None


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


profile_logger = logging.getLogger('profile_middleware')


class MemoryUsageMiddleware(object):
    """
    Stolen and modified from http://stackoverflow.com/a/12254394/8207

    This is a pretty poor, blunt tool and is not recommended to be treated as definitive truth.
    """
    _psutil_installed = None

    def _check_psutil(self):
        if self._psutil_installed is None:
            if psutil is None:
                profile_logger.warning('Install dev-requirements (psutil) in order to use MemoryUsageMiddleware')
                self._psutil_installed = False
            else:
                self._psutil_installed = True
        return self._psutil_installed

    def process_request(self, request):
        if self._check_psutil():
            request._profile_memory = psutil.Process(os.getpid()).get_memory_info()

    def process_response(self, request, response):
        if self._check_psutil() and hasattr(request, '_profile_memory'):
            mem = psutil.Process(os.getpid()).get_memory_info()
            diff = (mem.rss - request._profile_memory.rss) / 1024
            profile_logger.info('{} memory usage {} KB'.format(request.path, diff))
        return response


class TimingMiddleware(object):

    def process_request(self, request):
        request._profile_starttime = datetime.datetime.utcnow()

    def process_response(self, request, response):
        if hasattr(request, '_profile_starttime'):
            end = datetime.datetime.utcnow() - request._profile_starttime
            profile_logger.info('{} time {}'.format(request.path, end))
        return response
