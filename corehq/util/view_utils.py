import json
import logging
import traceback
from functools import wraps

from django import http
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.urls import reverse as _reverse
from django.utils.http import urlencode

from dimagi.utils.logging import notify_exception
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
        from . import as_text
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
            message = f'JSON exception response: {as_text(e)}'
            notify_exception(request, message)
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
    if exception.args and isinstance(exception.args[0], bytes):
        message = exception.args[0].decode('utf-8')
    else:
        message = str(exception)
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


def get_case_or_404(domain, case_id):
    from corehq.form_processor.exceptions import CaseNotFound
    from corehq.form_processor.models import CommCareCase
    try:
        case = CommCareCase.objects.get_case(case_id, domain)
        if case.domain != domain or case.is_deleted:
            # raise Http404()
            raise Exception("{} isn't equal to {} or something else was off".format(case.domain, domain))
        return case
    except CaseNotFound:
        # raise Http404()
        raise Exception("Case was simply not found?")


def get_form_or_404(domain, id):
    from corehq.form_processor.exceptions import XFormNotFound
    from corehq.form_processor.models import XFormInstance
    try:
        form = XFormInstance.objects.get_form(id, domain)
        if form.is_deleted:
            raise Http404()
        return form
    except XFormNotFound:
        raise Http404()


def request_as_dict(request):
    """
    Function returns the dictionary which contains the data of request object.
    :Parameter request:
            Object of HttpRequest

    :Return request_data:
            Dict containing the request data
    """

    # This is a parameter that is provided by middleware that may or may not exist
    can_access_all_locations = getattr(request, 'can_access_all_locations', False)

    request_data = dict(
        GET=request.GET if request.method == 'GET' else request.POST,
        META=dict(
            QUERY_STRING=request.META.get('QUERY_STRING'),
            PATH_INFO=request.META.get('PATH_INFO')
        ),
        datespan=request.datespan,
        couch_user=None,
        can_access_all_locations=can_access_all_locations
    )

    try:
        request_data.update(couch_user=request.couch_user.get_id)
    except Exception as e:
        logging.error("Could not pickle the couch_user id from the request object. Error: %s" % e)

    return request_data


def is_ajax(request):
    """Check if requested with XMLHttpRequest

    HttpRequest.is_ajax() was deprecated in Django 3.1
    https://docs.djangoproject.com/en/4.0/releases/3.1/#id2
    """
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'
