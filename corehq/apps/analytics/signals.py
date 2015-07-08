from corehq.apps.accounting.utils import ensure_domain_instance
from .tasks import identify

from django.dispatch import receiver

from corehq.apps.users.models import WebUser
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
        update_subscription_properties_by_user(couch_user)


@receiver(commcare_domain_post_save)
@receiver(subscription_upgrade_or_downgrade)
def domain_save_callback(sender, **kwargs):
    domain = kwargs.get("domain", None)
    domain = ensure_domain_instance(domain)
    if domain:
        update_subscription_properties_by_domain(domain)


def update_subscription_properties_by_user(couch_user):

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

    identify.delay(couch_user.username, properties)


def update_subscription_properties_by_domain(domain):
    affected_users = WebUser.view(
        'users/web_users_by_domain', reduce=False, key=domain.name, include_docs=True
    ).all()

    for web_user in affected_users:
        update_subscription_properties_by_user(web_user)
