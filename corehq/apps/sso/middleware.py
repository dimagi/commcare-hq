from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin

from corehq.apps.sso.exceptions import SingleSignOnError


class SingleSignOnErrorMiddleware(MiddlewareMixin):
    """
    Catches SingleSignOnError anywhere in view processing
    and shows a dedicated SSO error page instead of a 500.
    """

    def process_exception(self, request, exception):
        if isinstance(exception, SingleSignOnError):
            return render(
                request,
                'sso/sso_error.html',
                {'error': exception},
                status=503,
            )
