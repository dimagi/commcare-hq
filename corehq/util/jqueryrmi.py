# -*- coding: utf-8 -*-
"""jQuery RMI adaptor for Django

Used with [jquery.rmi](https://github.com/dimagi/jquery.rmi).

Original source (dead project):
https://github.com/jrief/django-angular/blob/666f4ee8e57a3c/djng/views/mixins.py
"""
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden

from corehq.util.view_utils import is_ajax


def allow_remote_invocation(func, method='auto'):
    """
    All methods which shall be callable through a given Ajax 'action' must be
    decorated with ``@allow_remote_invocation``. This is required for safety
    reasons. It inhibits the caller to invoke all available methods of a class.
    """
    setattr(func, 'allow_rmi', method)
    return func


class JSONResponseException(Exception):
    """
    Exception class for triggering HTTP 4XX responses with JSON content, where expected.
    """
    status_code = 400

    def __init__(self, message=None, status=None, *args, **kwargs):
        if status is not None:
            self.status_code = status
        super(JSONResponseException, self).__init__(message, *args, **kwargs)


class JSONResponseMixin:
    """
    A mixin for View classes that dispatches requests containing the private
    HTTP header ``HTTP_DJNG_REMOTE_METHOD`` onto a method of an instance of this
    class, with the given method name. This named method must be decorated with
    ``@allow_remote_invocation`` and shall return a value that is serializable
    to JSON.

    The returned HTTP responses are of kind ``application/json;charset=UTF-8``.
    """
    json_encoder = DjangoJSONEncoder
    json_content_type = 'application/json;charset=UTF-8'

    def get(self, request, *args, **kwargs):
        return self._invoke_remote_method(request, args, kwargs)

    def post(self, request, *args, **kwargs):
        def data():
            try:
                return json.loads(request.body.decode('utf-8'))
            except ValueError:
                return request.body.decode('utf-8')
        return self._invoke_remote_method(request, args, kwargs, data)

    def _invoke_remote_method(self, request, args, kwargs, data=None):
        if not is_ajax(request):
            return self._dispatch_super(request, *args, **kwargs)
        remote_method = request.META.get('HTTP_DJNG_REMOTE_METHOD')
        handler = remote_method and getattr(self, remote_method, None)
        if not callable(handler):
            return self._dispatch_super(request, *args, **kwargs)
        if not hasattr(handler, 'allow_rmi'):
            return HttpResponseForbidden(
                f"Method '{type(self).__name__}.{remote_method}' has no decorator '@allow_remote_invocation'")
        data_args = (data(),) if data is not None else ()
        try:
            response_data = handler(*data_args)
        except JSONResponseException as e:
            return self.json_response({'message': e.args[0]}, e.status_code)
        return self.json_response(response_data)

    def _dispatch_super(self, request, *args, **kwargs):
        base = super(JSONResponseMixin, self)
        handler = getattr(base, request.method.lower(), None)
        if callable(handler):
            return handler(request, *args, **kwargs)
        return HttpResponseBadRequest('This view can not handle method {0}'.format(request.method), status=405)

    def json_response(self, response_data, status=200, **kwargs):
        out_data = json.dumps(response_data, cls=self.json_encoder, **kwargs)
        response = HttpResponse(out_data, content_type=self.json_content_type, status=status)
        response['Cache-Control'] = 'no-cache'
        return response
