# -*- coding: utf-8 -*-
"""jQuery RMI adaptor for Django

Used with [jquery.rmi](https://github.com/dimagi/jquery.rmi).

Original source (dead project):
https://github.com/jrief/django-angular/blob/666f4ee8e57a3c/djng/views/mixins.py
"""
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden


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


class JSONBaseMixin(object):
    """
    Basic mixin for encoding HTTP responses in JSON format.
    """
    json_encoder = DjangoJSONEncoder
    json_content_type = 'application/json;charset=UTF-8'

    def json_response(self, response_data, status=200, **kwargs):
        out_data = json.dumps(response_data, cls=self.json_encoder, **kwargs)
        response = HttpResponse(out_data, self.json_content_type, status=status)
        response['Cache-Control'] = 'no-cache'
        return response


class JSONResponseMixin(JSONBaseMixin):
    """
    A mixin for View classes that dispatches requests containing the private HTTP header
    ``DjNg-Remote-Method`` onto a method of an instance of this class, with the given method name.
    This named method must be decorated with ``@allow_remote_invocation`` and shall return a
    list or dictionary which is serializable to JSON.
    The returned HTTP responses are of kind ``application/json;charset=UTF-8``.
    """
    def get(self, request, *args, **kwargs):
        if not request.is_ajax():
            return self._dispatch_super(request, *args, **kwargs)
        remote_method = request.META.get('HTTP_DJNG_REMOTE_METHOD')
        handler = remote_method and getattr(self, remote_method, None)
        if not callable(handler):
            return self._dispatch_super(request, *args, **kwargs)
        if not hasattr(handler, 'allow_rmi'):
            return HttpResponseForbidden("Method '{0}.{1}' has no decorator '@allow_remote_invocation'"
                                            .format(self.__class__.__name__, remote_method))
        try:
            response_data = handler()
        except JSONResponseException as e:
            return self.json_response({'message': e.args[0]}, e.status_code)
        return self.json_response(response_data)

    def post(self, request, *args, **kwargs):
        if not request.is_ajax():
            return self._dispatch_super(request, *args, **kwargs)
        try:
            in_data = json.loads(request.body.decode('utf-8'))
        except ValueError:
            in_data = request.body.decode('utf-8')
        remote_method = request.META.get('HTTP_DJNG_REMOTE_METHOD')
        handler = remote_method and getattr(self, remote_method, None)
        if not callable(handler):
            return self._dispatch_super(request, *args, **kwargs)
        if not hasattr(handler, 'allow_rmi'):
            return HttpResponseForbidden("Method '{0}.{1}' has no decorator '@allow_remote_invocation'"
                                         .format(self.__class__.__name__, remote_method), 403)
        try:
            response_data = handler(in_data)
        except JSONResponseException as e:
            return self.json_response({'message': e.args[0]}, e.status_code)
        return self.json_response(response_data)

    def _dispatch_super(self, request, *args, **kwargs):
        base = super(JSONResponseMixin, self)
        handler = getattr(base, request.method.lower(), None)
        if callable(handler):
            return handler(request, *args, **kwargs)
        return HttpResponseBadRequest('This view can not handle method {0}'.format(request.method), status=405)
