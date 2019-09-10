from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.urls import reverse

from corehq.apps.accounting.signals import subscription_upgrade_or_downgrade
from corehq.apps.analytics.tasks import (
    HUBSPOT_COOKIE,
    get_subscription_properties_by_user,
    identify,
    track_user_sign_in_on_hubspot,
    update_hubspot_properties,
    update_subscription_properties_by_domain,
)
from corehq.apps.analytics.utils import get_instance_string, get_meta
from corehq.apps.domain.signals import commcare_domain_post_save
from corehq.apps.registration.views import ProcessRegistrationView
from corehq.apps.users.models import CouchUser
from corehq.apps.users.signals import couch_user_post_save
from corehq.util.decorators import handle_uncaught_exceptions
from corehq.util.soft_assert import soft_assert

_no_cookie_soft_assert = soft_assert(to=['{}@{}'.format('cellowitz', 'dimagi.com'),
                                         '{}@{}'.format('biyeun', 'dimagi.com'),
                                         '{}@{}'.format('jschweers', 'dimagi.com')],
                                     send_to_ops=False)


@receiver(couch_user_post_save)
def user_save_callback(sender, **kwargs):
    couch_user = kwargs.get("couch_user", None)
    if couch_user and couch_user.is_web_user():
        properties = {}
        properties.update(get_subscription_properties_by_user(couch_user))
        properties.update(get_domain_membership_properties(couch_user))
        identify.delay(couch_user.username, properties)
        update_hubspot_properties.delay(couch_user, properties)


@receiver(commcare_domain_post_save)
@receiver(subscription_upgrade_or_downgrade)
def domain_save_callback(sender, domain, **kwargs):
    if isinstance(domain, str):
        domain_name = domain
    else:
        domain_name = domain.name
    update_subscription_properties_by_domain(domain_name)


def get_domain_membership_properties(couch_user):
    env = get_instance_string()

    return {
        "{}number_of_project_spaces".format(env): len(couch_user.domains),
        "{}project_spaces_list".format(env): '\n'.join(couch_user.domains),
    }


@receiver(user_logged_in)
@handle_uncaught_exceptions(mail_admins=True)
def track_user_login(sender, request, user, **kwargs):
    if settings.ANALYTICS_IDS.get('HUBSPOT_API_ID'):
        couch_user = CouchUser.from_django_user(user)
        if couch_user and couch_user.is_web_user():
            if not request or HUBSPOT_COOKIE not in request.COOKIES:
                # API calls, form submissions etc.

                user_confirming = request.path.startswith(reverse(ProcessRegistrationView.urlname))
                if user_confirming:
                    _no_cookie_soft_assert(False, 'User confirmed account but had no cookie')
                else:
                    return

            meta = get_meta(request)
            track_user_sign_in_on_hubspot.delay(couch_user, request.COOKIES.get(HUBSPOT_COOKIE),
                                                meta, request.path)
