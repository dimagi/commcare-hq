from django.conf import settings
from django.template.loader import render_to_string

from corehq.apps.accounting.utils import get_default_domain_url
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.util.global_request import get_request


def send_subscription_change_alert(domain, new_subscription, old_subscription, internal_change,
                                   change_type='Change'):

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
    email_subject = "{env}Subscription {change_type} Alert: {domain} from {old_plan} to {new_plan}".format(
        env=("[{}] ".format(settings.SERVER_ENVIRONMENT.upper())
             if settings.SERVER_ENVIRONMENT == "staging" else ""),
        change_type=change_type,
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
    send_subscription_change_alert(domain, new_subscription, old_subscription, False, change_type='Renewal')
