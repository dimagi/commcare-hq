from django.contrib import messages
from django.utils.translation import gettext as _

from corehq.apps.domain.exceptions import NameUnavailableException, ErrorInitializingDomain
from corehq.apps.registration.models import AsyncSignupRequest
from corehq.apps.registration.utils import request_new_domain


def process_async_signup_requests(request, user):
    # activate new project if needed
    async_signup = AsyncSignupRequest.get_by_username(user.username)
    if async_signup and async_signup.project_name:
        try:
            request_new_domain(
                request,
                async_signup.project_name,
                is_new_user=True,
                is_new_sso_user=True
            )
        except NameUnavailableException:
            # this should never happen, but in the off chance it does
            # we don't want to throw a 500 on this view
            messages.error(
                request,
                _("We were unable to create your requested project "
                  "because the name was already taken.")
            )
        except ErrorInitializingDomain:
            messages.error(
                request,
                _("We were unable to create your requested project "
                  "due to an unexpected issue. Please try again in a few minutes."
                  "If the issue persists, please contact support.")
            )

    AsyncSignupRequest.clear_data_for_username(user.username)
