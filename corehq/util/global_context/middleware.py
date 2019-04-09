from __future__ import absolute_import
from __future__ import unicode_literals

from django.utils.decorators import method_decorator
from django.utils.deprecation import MiddlewareMixin
from django.views.decorators.debug import sensitive_post_parameters

from .api import global_context


class GlobalContextMiddleware(MiddlewareMixin):

    @method_decorator(sensitive_post_parameters('password'))
    def process_request(self, request):
        global_context.request = request

    def process_response(self, request, response):
        global_context.reset()
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if hasattr(view_func, 'func_name'):
            fqview = "%s.%s" % (view_func.__module__, view_func.__name__)
        else:
            fqview = "%s.%s" % (view_func.__module__, view_func.__class__.__name__)
        global_context.context_key = fqview
