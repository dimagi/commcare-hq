from functools import wraps
import json
import inspect
import logging
import traceback
from django.core.urlresolvers import reverse
from dimagi.utils.web import get_url_base

from django import http
from django.conf import settings
from django.core.exceptions import PermissionDenied
from corehq.util import global_request

JSON = 'application/json'
logger = logging.getLogger('django.request')


def set_file_download(response, filename):
    response["Content-Disposition"] = 'attachment; filename="%s"' % filename


class BadRequest(Exception):
    """Error to be used with @json_error to signal a bad request

    Inspired by https://github.com/jsocol/django-jsonview ::

    HTTP does not have a great status code for "you submitted a form that didn't
    validate," and so Django doesn't support it very well. Most examples just
    return 200 OK.

    Normally, this is fine. But if you're submitting a form via Ajax, it's nice
    to have a distinct status for "OK" and "Nope." The HTTP 400 Bad Request
    response is the fallback for issues with a request not-otherwise-specified,
    so let's do that.

    To cause @json_error to return a 400, just raise this exception with
    whatever appropriate error message.
    """


def json_error(f):
    """A decorator for request handlers that returns structured error responses

    Inspired by (and some parts shamelessly copied from)
    https://github.com/jsocol/django-jsonview
    """
    @wraps(f)
    def inner(request, *args, **kwargs):
        try:
            response = f(request, *args, **kwargs)

            # Some errors are not exceptions. :\
            if isinstance(response, http.HttpResponseNotAllowed):
                blob = json.dumps({
                    'error': 405,
                    'message': 'HTTP method not allowed.'
                })
                return http.HttpResponse(blob, status=405, content_type=JSON)

            return response

        except http.Http404 as e:
            blob = json.dumps({
                'error': 404,
                'message': unicode(e),
            })
            logger.warning('Not found: %s', request.path,
                           extra={
                               'status_code': 404,
                               'request': request,
                           })
            return http.HttpResponseNotFound(blob, content_type=JSON)
        except PermissionDenied as e:
            logger.warning(
                'Forbidden (Permission denied): %s', request.path,
                extra={
                    'status_code': 403,
                    'request': request,
                })
            blob = json.dumps({
                'error': 403,
                'message': unicode(e),
            })
            return http.HttpResponseForbidden(blob, content_type=JSON)
        except BadRequest as e:
            blob = json.dumps({
                'error': 400,
                'message': unicode(e),
            })
            return http.HttpResponseBadRequest(blob, content_type=JSON)
        except Exception as e:
            data = {
                'error': 500,
                'message': unicode(e)
            }
            if settings.DEBUG:
                data['traceback'] = traceback.format_exc()
            return http.HttpResponse(
                status=500,
                content=json.dumps(data),
                content_type=JSON
            )
    return inner


def get_request():
    return global_request.get_request()


def absolute_reverse(*args, **kwargs):
    return "{}{}".format(get_url_base(), reverse(*args, **kwargs))
