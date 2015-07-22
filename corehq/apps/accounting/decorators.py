from functools import wraps
import json
from django.contrib import messages
from django.utils.encoding import force_unicode
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext
from corehq import privileges
from corehq.apps.accounting.models import DefaultProductPlan, \
    SoftwarePlanVisibility
from django.http import Http404, HttpResponse
from corehq.const import USER_DATE_FORMAT
from django_prbac.decorators import requires_privilege
from django_prbac.exceptions import PermissionDenied


def requires_privilege_with_fallback(slug, **assignment):
    """
    A version of the requires_privilege decorator which falls back
    to the insufficient privileges page with an HTTP Status Code
    of 402 that means "Payment Required"
    """
    def decorate(fn):
        @wraps(fn)
        def wrapped(request, *args, **kwargs):
            try:
                if (hasattr(request, 'subscription')
                    and request.subscription is not None
                    and (request.subscription.is_trial or request.subscription.plan_version.plan.visibility == SoftwarePlanVisibility.TRIAL_INTERNAL)
                    and request.subscription.date_end is not None
                ):
                    edition_req = DefaultProductPlan.get_lowest_edition_by_domain(
                        request.domain, [slug]
                    )
                    plan_name = request.subscription.plan_version.user_facing_description['name']
                    feature_name = privileges.Titles.get_name_from_privilege(slug)
                    request.show_trial_notice = True
                    request.trial_info = {
                        'current_plan': plan_name,
                        'feature_name': feature_name,
                        'required_plan': edition_req,
                        'date_end': request.subscription.date_end.strftime(USER_DATE_FORMAT)
                    }
                    request.is_domain_admin = (hasattr(request, 'couch_user') and
                                               request.couch_user.is_domain_admin(request.domain))

                return requires_privilege(slug, **assignment)(fn)(
                    request, *args, **kwargs
                )
            except PermissionDenied:
                request.show_trial_notice = False
                from corehq.apps.domain.views import SubscriptionUpgradeRequiredView
                return SubscriptionUpgradeRequiredView().get(
                    request, request.domain, slug
                )
        return wrapped
    return decorate


def requires_privilege_plaintext_response(slug,
                                          http_status_code=None, **assignment):
    """
    A version of the requires_privilege decorator which returns an
    HttpResponse object with HTTP Status Code of 412 by default and
    content_type of tex/plain if the privilege is not found.
    """
    def decorate(fn):
        @wraps(fn)
        def wrapped(request, *args, **kwargs):
            try:
                return requires_privilege(slug, **assignment)(fn)(
                    request, *args, **kwargs
                )
            except PermissionDenied:
                return HttpResponse(
                    "You have lost access to this feature.",
                    status=http_status_code or 412, content_type="text/plain",
                )
        return wrapped
    return decorate


def requires_privilege_json_response(slug, http_status_code=None,
                                     get_response=None, **assignment):
    """
    A version of the requires privilege decorator which returns an
    HttpResponse object with an HTTP Status Code of 405 by default
    and content_type application/json if the privilege is not found.

    `get_response` is an optional parameter where you can specify the
    format of response given an error message and status code.
    The default response is:
    ```
    {
        'code': http_status_Code,
        'message': error_message
    }
    ```
    todo accounting for API requests
    """
    http_status_code = http_status_code or 405
    if get_response is None:
        get_response = lambda msg, code: {'code': code, 'message': msg}

    def decorate(fn):
        @wraps(fn)
        def wrapped(request, *args, **kwargs):
            try:
                return requires_privilege(slug, **assignment)(fn)(
                    request, *args, **kwargs)
            except PermissionDenied:
                error_message = "You have lost access to this feature."
                response = get_response(error_message, http_status_code)
                return HttpResponse(json.dumps(response),
                                    content_type="application/json")
        return wrapped
    return decorate


def requires_privilege_for_commcare_user(slug, **assignment):
    """
    A version of the requires_privilege decorator which requires
    the specified privilege only for CommCareUsers.
    """
    def decorate(fn):
        @wraps(fn)
        def wrapped(request, *args, **kwargs):
            if (hasattr(request, 'couch_user')
                    and request.couch_user.is_web_user()):
                return fn(request, *args, **kwargs)
            return requires_privilege_with_fallback(slug, **assignment)(fn)(
                request, *args, **kwargs
            )
        return wrapped
    return decorate
