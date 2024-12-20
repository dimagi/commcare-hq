from django.http import HttpResponseForbidden, HttpResponse

ANY_METHOD = 'any_method'


class HqHtmxActionMixin:
    """
    A mixin for TemplateView classes that dispatches requests from HTMX where
    the triggering element has the ``hq-hx-action`` attribute specified and
    the ``HTTP_HQ_HX_ACTION`` is present (HQ-HX-Action in the header)

    The dispatch method will then route the action request to the method in the
    class with the same name as the slug present in ``hq-hx-action``.

    A security requirement is that the receiving method must be decorated with ``@hq_hx_action()``

    Each method decorated with ``hq_hx_action`` should receive the following arguments:
        ``request``, ``*args``, ``**kwargs``

    It should return a template response using:
        - ``super().get(request, *args, **kwargs)``, or an equivalent method supported by the `TemplateView`
        - ``self.render_htmx_no_response(request, *args, **kwargs)`` if no response is required
        - ``self.render_htmx_partial_response(request, template, context)`` if a partial template
          response is required that is different from the template in ``self.template_name``

    Example trigger element in requesting HTML:

        <div hq-hx-action="make_edit" hx-post="{{ url_to_view }}"...></div>

    Example usage in receiving TemplateView:

        @hq_hx_action()
        def make_edit(request, *args, **kwargs):
            ...
            return super().get(request, *args, **kwargs)

    To limit requests to a specific HTTP method, specify the method type in ``@hq_hx_action``.
    For instance, to limit requests to ``POST``:

        @hq_hx_action('post')
        def make_edit(request, *args, **kwargs):
            ...
            return super().get(request, *args, **kwargs)

    To raise exceptions in these HTMX action responses, you can raise an ``HtmxResponseException``
    and override either ``default_htmx_error_template`` and/or ``get_htmx_error_template``
    to return the appropriate error template based on the HTMX Action.

    Example docs here: commcarehq.org/styleguide/b5/htmx_alpine/
    See working demo here: commcarehq.org/styleguide/demo/htmx_todo/
    """
    default_htmx_error_template = "hqwebapp/htmx/htmx_action_error.html"

    def get_htmx_error_context(self, action, htmx_error, **kwargs):
        """
        Use this method to return the context for the HTMX error template.

        :param action: string (the slug for the HTMX action taken)
        :param htmx_error: HtmxResponseException
        :return: dict
        """
        return {
            "action": action,
            "htmx_error": htmx_error,
        }

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
        action = request.META.get('HTTP_HQ_HX_ACTION')
        if not action:
            return super().dispatch(request, *args, **kwargs)

        handler = getattr(self, action, None)
        if not callable(handler):
            return HtmxResponseForbidden(
                f"Method '{type(self).__name__}.{action}' "
                f"does not exist"
            )

        action_method = getattr(handler, "hq_hx_action", None)
        if not action_method:
            return HtmxResponseForbidden(
                f"Method '{type(self).__name__}.{action}' has no "
                f"@hq_hx_action decorator."
            )

        if action_method != ANY_METHOD and action_method.lower() != request.method.lower():
            return HtmxResponseForbidden(
                f"Method '{type(self).__name__}.{action}' is not allowed to use "
                f"HTTP {request.method} requests."
            )

        try:
            response = handler(request, *args, **kwargs)
        except HtmxResponseException as err:
            context = self.get_htmx_error_context(action, err, **kwargs)
            self.template_name = self.get_htmx_error_template(action, err)
            return self.render_to_response(context)
        return response


def hq_hx_action(method=ANY_METHOD):
    """
    All methods that can be referenced from the value of an `hq-hx-action` attribute
    must be decorated with ``@hq_hx_action``.

    See ``HqHtmxActionMixin`` docstring for usage examples.
    """
    def decorator(func):
        setattr(func, 'hq_hx_action', method)
        return func
    return decorator


class HtmxResponseForbidden(HttpResponseForbidden):

    def __init__(self, error_message, *args, **kwargs):
        super().__init__(
            error_message,
            reason=f"Forbidden: {error_message}",
            *args,
            **kwargs
        )


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
