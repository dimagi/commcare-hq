from __future__ import absolute_import
from django.contrib.auth.signals import user_logged_in
from corehq.apps.accounting.utils import ensure_domain_instance
from corehq.apps.analytics.tasks import (
    track_user_sign_in_on_hubspot,
    HUBSPOT_COOKIE,
    update_hubspot_properties,
)
from corehq.apps.analytics.utils import get_meta
from corehq.apps.registration.views import ProcessRegistrationView
from corehq.util.decorators import handle_uncaught_exceptions
from corehq.util.soft_assert import soft_assert
from .tasks import identify

from django.dispatch import receiver
from django.urls import reverse


from corehq.apps.users.models import WebUser, CouchUser
from corehq.apps.accounting.models import (
    DefaultProductPlan,
    ProBonoStatus,
    SoftwarePlanEdition,
    SoftwarePlanVisibility,
    Subscription,
    SubscriptionType,
)
from corehq.apps.accounting.signals import subscription_upgrade_or_downgrade
from corehq.apps.domain.signals import commcare_domain_post_save
from corehq.apps.users.signals import couch_user_post_save
from corehq.apps.analytics.utils import get_instance_string


_no_cookie_soft_assert = soft_assert('{}@{}'.format('cellowitz', 'dimagi.com'), send_to_ops=False)


@receiver(couch_user_post_save)
def user_save_callback(sender, **kwargs):
    couch_user = kwargs.get("couch_user", None)
    if couch_user and couch_user.is_web_user():
        properties = {}
        properties.update(get_subscription_properties_by_user(couch_user))
        properties.update(get_domain_membership_properties(couch_user))
        identify.delay(couch_user.username, properties)
        update_hubspot_properties(couch_user, properties)


@receiver(commcare_domain_post_save)
@receiver(subscription_upgrade_or_downgrade)
def domain_save_callback(sender, domain, **kwargs):
    domain = ensure_domain_instance(domain)
    if domain:
        update_subscription_properties_by_domain(domain)


def update_subscription_properties_by_user(couch_user):
    properties = get_subscription_properties_by_user(couch_user)
    identify.delay(couch_user.username, properties)
    update_hubspot_properties(couch_user, properties)


def get_subscription_properties_by_user(couch_user):

    def _is_paying_subscription(subscription, plan_version):
        NON_PAYING_SERVICE_TYPES = [
            SubscriptionType.TRIAL,
            SubscriptionType.EXTENDED_TRIAL,
            SubscriptionType.SANDBOX,
            SubscriptionType.INTERNAL,
        ]

        NON_PAYING_PRO_BONO_STATUSES = [
            ProBonoStatus.YES,
            ProBonoStatus.DISCOUNTED,
        ]
        return (plan_version.plan.visibility != SoftwarePlanVisibility.TRIAL and
                subscription.service_type not in NON_PAYING_SERVICE_TYPES and
                subscription.pro_bono_status not in NON_PAYING_PRO_BONO_STATUSES and
                plan_version.plan.edition != SoftwarePlanEdition.COMMUNITY)


    # Note: using "yes" and "no" instead of True and False because spec calls
    # for using these values. (True is just converted to "True" in KISSmetrics)
    all_subscriptions = []
    paying_subscribed_editions = []
    subscribed_editions = []
    for domain_name in couch_user.domains:
        subscription = Subscription.get_active_subscription_by_domain(domain_name)
        plan_version = (
            subscription.plan_version
            if subscription is not None
            else DefaultProductPlan.get_default_plan_version()
        )
        subscribed_editions.append(plan_version.plan.edition)
        if subscription is not None:
            all_subscriptions.append(subscription)
        if subscription is not None and _is_paying_subscription(subscription, plan_version):
            paying_subscribed_editions.append(plan_version.plan.edition)

    def _is_one_of_editions(edition):
        return 'yes' if edition in subscribed_editions else 'no'

    def _is_a_pro_bono_status(status):
        return 'yes' if status in [s.pro_bono_status for s in all_subscriptions] else 'no'

    def _is_on_extended_trial():
        service_types = [s.service_type for s in all_subscriptions]
        return 'yes' if SubscriptionType.EXTENDED_TRIAL in service_types else 'no'

    def _max_edition():
        for edition in paying_subscribed_editions:
            assert edition in [e[0] for e in SoftwarePlanEdition.CHOICES]

        return max(paying_subscribed_editions) if paying_subscribed_editions else ''

    env = get_instance_string()

    return {
        '{}is_on_community_plan'.format(env): _is_one_of_editions(SoftwarePlanEdition.COMMUNITY),
        '{}is_on_standard_plan'.format(env): _is_one_of_editions(SoftwarePlanEdition.STANDARD),
        '{}is_on_pro_plan'.format(env): _is_one_of_editions(SoftwarePlanEdition.PRO),
        '{}is_on_pro_bono_plan'.format(env): _is_a_pro_bono_status(ProBonoStatus.YES),
        '{}is_on_discounted_plan'.format(env): _is_a_pro_bono_status(ProBonoStatus.DISCOUNTED),
        '{}is_on_extended_trial_plan'.format(env): _is_on_extended_trial(),
        '{}max_edition_of_paying_plan'.format(env): _max_edition()
    }


def get_domain_membership_properties(couch_user):
    env = get_instance_string()

    return {
        "{}number_of_project_spaces".format(env): len(couch_user.domains),
        "{}project_spaces_list".format(env): '\n'.join(couch_user.domains),
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

            user_confirming = request.path.startswith(reverse(ProcessRegistrationView.urlname))
            if user_confirming:
                _no_cookie_soft_assert(False, 'User confirmed account but had no cookie')
            else:
                return

        meta = get_meta(request)
        track_user_sign_in_on_hubspot.delay(couch_user, request.COOKIES, meta, request.path)
