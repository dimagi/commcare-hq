from __future__ import absolute_import
from __future__ import unicode_literals
import json

from django.http import HttpResponse, HttpRequest
from django.utils.functional import cached_property

import six


class AsyncHandlerMixin(object):
    """
    To be mixed in with a TemplateView.
    todo write better documentation on this (biyeun)
    """
    async_handlers = []

    @property
    def handler_slug(self):
        return self.request.POST.get('handler')

    def get_async_handler(self):
        handler_class = dict([(h.slug, h) for h in self.async_handlers])[self.handler_slug]
        return handler_class(self.request)

    @cached_property
    def async_response(self):
        if self.handler_slug in [h.slug for h in self.async_handlers]:
            return self.get_async_handler().get_response()


class AsyncHandlerError(Exception):
    pass


class BaseAsyncHandler(object):
    """
    Handles serving async responses for an ajax post request, say in a form.
    Usage:
    1) specify an allowed action slug in allowed actions
    2) implement the property <allowed action slug>_response, which returns a dict.
    example:

    allowed_actions = [
        'create'
    ]
    then implement

    @property
    def create_response(self):
        return {}

    """
    slug = None
    allowed_actions = []

    def __init__(self, request):
        if not isinstance(request, HttpRequest):
            raise ValueError("request must be an HttpRequest.")
        self.request = request
        self.data = request.POST if request.method == 'POST' else request.GET
        self.action = self.data.get('action')
        # When used with the javascript baseSelect2Handler, some field names might have hyphens,
        # for example if the Django form has a 'prefix' attribute specified.
        # Convert hyphens to underscores for the purposes of this integration, since python method
        # names can't have hyphens.
        if self.action:
            self.action = self.action.replace('-', '_')

    def _fmt_error(self, error):
        return json.dumps({
            'success': False,
            'error': six.text_type(error),
        })

    def _fmt_success(self, data):
        return json.dumps({
            'success': True,
            'data': data,
        })

    def get_action_response(self):
        if self.action not in self.allowed_actions:
            raise AsyncHandlerError("Action '%s' is not allowed." % self.action)
        response = getattr(self, '%s_response' % self.action)
        return self._fmt_success(response)

    def get_response(self):
        try:
            response = self.get_action_response()
        except AsyncHandlerError as e:
            response = self._fmt_error(e)
        except TypeError as e:
            response = self._fmt_error(e)
        return HttpResponse(response, content_type='application/json')
