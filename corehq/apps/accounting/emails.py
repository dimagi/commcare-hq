from django.conf import settings
from django.template.loader import render_to_string

from corehq.apps.accounting.utils import get_default_domain_url
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.util.global_request import get_request


class SubjectTemplate:
    CHANGE = "{env}Subscription Change Alert: {domain} from {old_plan} to {new_plan}"
    RENEW = "{env}Subscription Renewal Alert: {domain} from {old_plan} to {new_plan}"
    SELF_START = "{env}New Self-Start Subscription Alert: {domain} to {new_plan}"


def send_subscription_change_alert(domain, new_subscription, old_subscription, internal_change=False,
                                   subject_template=SubjectTemplate.CHANGE):

    billing_account = (
        new_subscription.account if new_subscription else
        old_subscription.account if old_subscription else None
    )
    # this can be None, though usually this will be initiated
    # by an http request
    request = get_request()
    email_context = {
        'domain': domain,
        'domain_url': get_default_domain_url(domain),
        'old_plan': old_subscription.plan_version if old_subscription else None,
        'new_plan': new_subscription.plan_version if new_subscription else None,
        'old_subscription': old_subscription,
        'new_subscription': new_subscription,
        'billing_account': billing_account,
        'username': request.couch_user.username if getattr(request, 'couch_user', None) else None,
        'referer': request.META.get('HTTP_REFERER') if request else None,
    }
    email_subject = subject_template.format(
        env=("[{}] ".format(settings.SERVER_ENVIRONMENT.upper())
             if settings.SERVER_ENVIRONMENT == "staging" else ""),
        domain=email_context['domain'],
        old_plan=email_context['old_plan'],
        new_plan=email_context['new_plan'],
    )

    sub_change_email_address = (settings.INTERNAL_SUBSCRIPTION_CHANGE_EMAIL
                                if internal_change else settings.SUBSCRIPTION_CHANGE_EMAIL)

    send_html_email_async.delay(
        email_subject,
        sub_change_email_address,
        render_to_string('accounting/email/subscription_change.html', email_context),
        text_content=render_to_string('accounting/email/subscription_change.txt', email_context),
    )


def send_subscription_renewal_alert(domain, new_subscription, old_subscription):
    send_subscription_change_alert(domain, new_subscription, old_subscription,
                                   subject_template=SubjectTemplate.RENEW)


def send_self_start_subscription_alert(domain, new_subscription, old_subscription):
    send_subscription_change_alert(domain, new_subscription, old_subscription,
                                   subject_template=SubjectTemplate.SELF_START)
