import json
import logging

from django.http import HttpResponse, HttpResponseForbidden
from django.utils.encoding import force_str

from corehq.util.htmx_gtm import get_htmx_gtm_event

ANY_METHOD = 'any_method'
logger = logging.getLogger(__name__)


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

    To raise exceptions in these HTMX action responses, you can raise an ``HtmxResponseException``,
    which will be caught by the htmx:responseError event listener.

    Example docs here: commcarehq.org/styleguide/b5/htmx_alpine/
    See working demo here: commcarehq.org/styleguide/demo/htmx_todo/
    """

    def render_htmx_redirect(self, url, response_message=None):
        response = HttpResponse(response_message or "")
        response['HX-Redirect'] = url
        return response

    @staticmethod
    def _get_existing_hx_triggers(response):
        """
        Get existing HX-Trigger from the response headers.
        If it exists, parse it as JSON and return it as a dictionary.
        """
        existing = response.get('HX-Trigger', None)
        if existing:
            try:
                raw = force_str(existing)
                triggers = json.loads(raw)
            except (ValueError, TypeError):
                logger.warning(f"Couldn't parse HX-Trigger header: {existing}")
                triggers = {}
            if not isinstance(triggers, dict):
                triggers = {}
        else:
            triggers = {}
        return triggers

    def include_gtm_event_with_response(self, response, event_name, event_data=None):
        """
        Add a GTM event to the HTMX response headers.
        """
        triggers = self._get_existing_hx_triggers(response)
        if not event_data:
            event_data = {}
        triggers.update(get_htmx_gtm_event(event_name, event_data))
        response["HX-Trigger"] = json.dumps(triggers)
        return response

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
            try:
                return super().dispatch(request, *args, **kwargs)
            except HtmxResponseException as err:
                return self._return_error_response(err)

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
            return self._return_error_response(err, action=action)
        return response

    def _return_error_response(self, htmx_response_error, action=None):
        """
        Return a response for HTMX errors we want to handle gracefully
        on the client side.
        """
        response = HttpResponse(htmx_response_error.message, status=htmx_response_error.status_code)
        response['HQ-HX-Action-Error'] = json.dumps(
            {
                'message': htmx_response_error.message,
                'status_code': htmx_response_error.status_code,
                'retry_after': htmx_response_error.retry_after,
                'show_details': htmx_response_error.show_details,
                'max_retries': htmx_response_error.max_retries,
                'action': action,
            }
        )
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

    def __init__(
        self, message=None, status_code=None, retry_after=None, show_details=False, max_retries=20, *args, **kwargs
    ):
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.retry_after = retry_after  # in milliseconds
        self.show_details = show_details
        self.max_retries = max_retries
        super().__init__(*args, **kwargs)
