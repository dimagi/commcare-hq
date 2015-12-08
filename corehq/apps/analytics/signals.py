from django.contrib.auth.signals import user_logged_in
from corehq.apps.accounting.utils import ensure_domain_instance
from corehq.apps.analytics.tasks import (
    track_user_sign_in_on_hubspot,
    HUBSPOT_COOKIE,
    update_hubspot_properties,
)
from corehq.apps.analytics.utils import get_meta
from corehq.util.decorators import handle_uncaught_exceptions
from .tasks import identify

from django.dispatch import receiver

from corehq.apps.users.models import WebUser, CouchUser
from corehq.apps.accounting.models import (
    ProBonoStatus,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.accounting.signals import subscription_upgrade_or_downgrade
from corehq.apps.domain.signals import commcare_domain_post_save
from corehq.apps.users.signals import couch_user_post_save


@receiver(couch_user_post_save)
def user_save_callback(sender, **kwargs):
    couch_user = kwargs.get("couch_user", None)
    if couch_user and couch_user.is_web_user():
        properties = {}
        properties.update(_get_subscription_properties_by_user(couch_user))
        properties.update(_get_user_domain_memberships(couch_user))
        identify.delay(couch_user.username, properties)
        update_hubspot_properties(couch_user, properties)


@receiver(commcare_domain_post_save)
@receiver(subscription_upgrade_or_downgrade)
def domain_save_callback(sender, domain, **kwargs):
    domain = ensure_domain_instance(domain)
    if domain:
        update_subscription_properties_by_domain(domain)


def update_subscription_properties_by_user(couch_user):
    properties = _get_subscription_properties_by_user(couch_user)
    identify.delay(couch_user.username, properties)
    update_hubspot_properties(couch_user, properties)


def _get_subscription_properties_by_user(couch_user):

    # Note: using "yes" and "no" instead of True and False because spec calls
    # for using these values. (True is just converted to "True" in KISSmetrics)
    all_subscriptions = []
    subscribed_editions = []
    for domain_name in couch_user.domains:
        plan_version, subscription = Subscription.get_subscribed_plan_by_domain(domain_name)
        subscribed_editions.append(plan_version.plan.edition)
        if subscription is not None:
            all_subscriptions.append(subscription)

    def _is_one_of_editions(edition):
        return 'yes' if edition in subscribed_editions else 'no'

    def _is_a_pro_bono_status(status):
        return 'yes' if status in [s.pro_bono_status for s in all_subscriptions] else 'no'

    return {
        'is_on_community_plan': _is_one_of_editions(SoftwarePlanEdition.COMMUNITY),
        'is_on_standard_plan': _is_one_of_editions(SoftwarePlanEdition.STANDARD),
        'is_on_pro_plan': _is_one_of_editions(SoftwarePlanEdition.PRO),
        'is_on_advanced_plan': _is_one_of_editions(SoftwarePlanEdition.ADVANCED),
        'is_on_enterprise_plan': _is_one_of_editions(SoftwarePlanEdition.ENTERPRISE),
        'is_on_pro_bono_or_discounted_plan': _is_a_pro_bono_status(ProBonoStatus.YES),
    }


def _get_user_domain_memberships(couch_user):
    return {
        "number_of_project_spaces": len(couch_user.domains)
    }


def update_subscription_properties_by_domain(domain):
    affected_users = WebUser.view(
        'users/web_users_by_domain', reduce=False, key=domain.name, include_docs=True
    ).all()

    for web_user in affected_users:
        update_subscription_properties_by_user(web_user)


@receiver(user_logged_in)
@handle_uncaught_exceptions(mail_admins=True)
def track_user_login(sender, request, user, **kwargs):
    couch_user = CouchUser.from_django_user(user)
    if couch_user and couch_user.is_web_user():
        if not request or HUBSPOT_COOKIE not in request.COOKIES:
            # API calls, form submissions etc.
            return

        meta = get_meta(request)
        track_user_sign_in_on_hubspot.delay(couch_user, request.COOKIES, meta)
