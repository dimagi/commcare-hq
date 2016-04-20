import json
import logging
import traceback
from functools import wraps

from django import http
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse as _reverse
from django.utils.http import urlencode

from dimagi.utils.web import get_url_base

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
            return _get_json_exception_response(404, request, e, log_message='Not found: %s')
        except PermissionDenied as e:
            return _get_json_exception_response(403, request, e, log_message='Forbidden (Permission denied): %s')
        except BadRequest as e:
            return _get_json_exception_response(400, request, e)
        except Exception as e:
            return _get_json_exception_response(500, request, e)
    return inner


def _get_json_exception_response(code, request, exception, log_message=None):
    if log_message:
        logger.warning(
            log_message, request.path,
            extra={
                'status_code': code,
                'request': request,
            })

    data = _json_exception_response_data(code, exception)

    return http.HttpResponse(
        status=code,
        content=json.dumps(data),
        content_type=JSON
    )


def _json_exception_response_data(code, exception):
    if isinstance(exception.message, unicode):
        message = unicode(exception)
    else:
        message = str(exception).decode('utf-8')
    data = {
        'error': code,
        'message': message
    }
    if code == 500 and settings.DEBUG:
        data['traceback'] = traceback.format_exc()
    return data


def get_request():
    return global_request.get_request()


def reverse(viewname, params=None, absolute=False, **kwargs):
    """
    >>> reverse('create_location', args=["test"], params={"selected": "foo"})
    '/a/test/settings/locations/new/?selected=foo'
    """
    url = _reverse(viewname, **kwargs)
    if absolute:
        url = "{}{}".format(get_url_base(), url)
    if params:
        url = "{}?{}".format(url, urlencode(params))
    return url


def absolute_reverse(*args, **kwargs):
    return reverse(*args, absolute=True, **kwargs)
