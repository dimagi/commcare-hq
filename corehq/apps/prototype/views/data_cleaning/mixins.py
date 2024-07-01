from django.http import HttpResponseForbidden, HttpResponse


def hx_action(method='auto'):
    """
    All methods which shall be callable through a given HTMX `hx_action` must be
    decorated with ``@hx_action``.
    """
    def decorator(func):
        setattr(func, 'hx_action', method)
        return func
    return decorator


class HtmxResponseException(Exception):
    """
    Exception class for triggering HTTP 4XX responses for HTMX responses, where expected.
    """
    status_code = 400
    message = None

    def __init__(self, message=None, status=None, *args, **kwargs):
        self.message = message
        if status is not None:
            self.status_code = status
        super().__init__(*args, **kwargs)


class HtmxActionMixin:
    """
    A mixin for TemplateView classes that dispatches requests from HTMX where
    the triggering element has the ``hx-action`` attribute specified and
    the ``HTTP_HX_ACTION`` is present.

    The dispatch method will then route the action request to the instance
    method with the same name as the slug present in hx-action. A security requirement
    is that the receiving method must be decorated with @hx_action()

    The method will receive the arguments ``request``, ``*args``, ``**kwargs`` and
    should return a template response using ``self.render_to_response(context)``,
    ``super().get(request, *args, **kwargs)``, or an equivalent method.

    Example trigger element in requesting HTML:
        <div hx-action="make_edit" hx-post="{{ url_to_view }}"...></div>

    Example usage in receiving TemplateView:
        @htmx_action()
        def make_edit(request, *args, **kwargs):
            ...
            return super().get(request, *args, **kwargs)

    To limit requests to a specific HTTP method, specify the method type in ``@htmx_action``.
    For instance, to limit requests to ``POST``:
        @htmx_action('post')
        def make_edit(request, *args, **kwargs):
            ...
            return super().get(request, *args, **kwargs)

    To raise exceptions in these HTMX action responses, you can raise an ``HtmxResponseException``
    and override either ``default_htmx_error_template`` and/or ``get_htmx_error_template``
    to return the appropriate error template based on the HTMX Action.
    """
    default_htmx_error_template = "prototype/htmx/partials/htmx_action_error.html"

    def get_htmx_error_context(self, **kwargs):
        """
        Use this method to return the context for the HTMX error template.
        :return: dict
        """
        return {}

    def get_htmx_error_template(self, action, htmx_error):
        """
        Use this method to return the appropriate error template
        based on the htmx error received.
        :param action: string (the slug for the HTMX action taken)
        :param htmx_error: HtmxResponseException
        :return: string (path to template)
        """
        return self.default_htmx_error_template

    def render_htmx_no_response(self, request, *args, **kwargs):
        """
        Return this when the HTMX triggering element uses
        ``hx-swap="none"`` and there is no need to do additional view processing.
        """
        return HttpResponse("HTMX Response Successful")

    def render_htmx_partial_response(self, request, template, context):
        """
        Return this when a partial template response separate from the parent class's
        template should be returned.
        """
        return self.response_class(
            request=request,
            template=template,
            context=context,
            using=self.template_engine,
            content_type=self.content_type
        )

    def dispatch(self, request, *args, **kwargs):
        action = request.META.get('HTTP_HX_ACTION')
        if not action:
            return super().dispatch(request, *args, **kwargs)

        handler = getattr(self, action, None)
        if not callable(handler):
            return super().dispatch(request, *args, **kwargs)

        action_method = getattr(handler, "hx_action", None)
        if not action_method:
            return HttpResponseForbidden(
                f"Method '{type(self).__name__}.{action}' has no "
                f"decorator '@hx_action'"
            )

        if action_method != 'auto' and action_method.lower() != request.method.lower():
            return HttpResponseForbidden(
                f"Method '{type(self).__name__}.{action}' is not allowed for "
                f"HTTP {request.method} requests."
            )

        try:
            response = handler(request, *args, **kwargs)
        except HtmxResponseException as err:
            context = self.get_htmx_error_context(**kwargs)
            context["htmx_error"] = err
            self.template_name = self.get_htmx_error_template(action, err)
            return self.render_to_response(context)
        return response
