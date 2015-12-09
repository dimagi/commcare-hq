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
    properties = {
        SoftwarePlanEdition.COMMUNITY: "no",
        SoftwarePlanEdition.STANDARD: "no",
        SoftwarePlanEdition.PRO: "no",
        SoftwarePlanEdition.ADVANCED: "no",
        SoftwarePlanEdition.ENTERPRISE: "no",
        "Pro Bono": "no",
    }

    for domain_name in couch_user.domains:
        plan_version, subscription = Subscription.get_subscribed_plan_by_domain(domain_name)
        if subscription is not None:
            if subscription.pro_bono_status == ProBonoStatus.YES:
                properties["Pro Bono"] = "yes"
        edition = plan_version.plan.edition
        if edition in properties:
            properties[edition] = "yes"
    return {
        'is_on_community_plan': properties[SoftwarePlanEdition.COMMUNITY],
        'is_on_standard_plan': properties[SoftwarePlanEdition.STANDARD],
        'is_on_pro_plan': properties[SoftwarePlanEdition.PRO],
        'is_on_advanced_plan': properties[SoftwarePlanEdition.ADVANCED],
        'is_on_enterprise_plan': properties[SoftwarePlanEdition.ENTERPRISE],
        'is_on_pro_bono_or_discounted_plan': properties["Pro Bono"],
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
