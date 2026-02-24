from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from dimagi.utils.web import get_site_domain

from corehq.apps.accounting.exceptions import SubscriptionReminderError
from corehq.apps.accounting.utils import (
    get_default_domain_url,
    get_dimagi_from_email,
    log_accounting_info,
)
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.const import USER_DATE_FORMAT
from corehq.util.global_request import get_request
from corehq.util.soft_assert import soft_assert
from corehq.util.view_utils import absolute_reverse

_soft_assert_contact_emails_missing = soft_assert(
    to=['{}@{}'.format(email, 'dimagi.com') for email in [
        'accounts',
        'billing-dev',
    ]],
    exponential_backoff=False,
)


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


def send_flagged_pay_annually_subscription_alert(subscription, current_invoice, prepay_invoice):
    domain = subscription.subscriber.domain

    email_context = {
        'domain': domain,
        'domain_url': get_default_domain_url(domain),
        'plan_version': subscription.plan_version,
        'subscription': subscription,
        'billing_account': subscription.account,
        'current_invoice': current_invoice,
        'prepay_invoice': prepay_invoice,
    }

    subject_template = "{env}Pay Annually Alert: Product Fees Not Credited for {domain}"
    email_subject = subject_template.format(
        env=("[{}] ".format(settings.SERVER_ENVIRONMENT.upper())
             if settings.SERVER_ENVIRONMENT == "staging" else ""),
        domain=email_context['domain'],
    )

    sub_change_email_address = settings.SUBSCRIPTION_CHANGE_EMAIL

    send_html_email_async.delay(
        email_subject,
        sub_change_email_address,
        render_to_string('accounting/email/pay_annually_unpaid.html', email_context),
        text_content=render_to_string('accounting/email/pay_annually_unpaid.txt', email_context),
    )


def send_subscription_renewed_email(subscription):
    from corehq.apps.domain.views import DomainSubscriptionView

    to, cc, bcc = _get_reminder_email_contacts(subscription, subscription.subscriber.domain)
    template = 'accounting/email/subscription_renewed.html'
    template_plaintext = 'accounting/email/subscription_renewed.txt'

    context = {
        'domain': subscription.subscriber.domain,
        'plan': subscription.plan_version.plan.name,
        'date_start': subscription.date_start.strftime(USER_DATE_FORMAT),
        'subscription_url': absolute_reverse(
            DomainSubscriptionView.urlname, args=[subscription.subscriber.domain]
        ),
        'base_url': get_site_domain(),
    }
    subject = _(
        "CommCare Alert: {domain}'s subscription to {plan} automatically renewed for {date_start}"
    ).format(domain=context['domain'], plan=context['plan'], date_start=context['date_start'])

    email_html = render_to_string(template, context)
    email_plaintext = render_to_string(template_plaintext, context)
    send_html_email_async.delay(
        subject, to, email_html,
        text_content=email_plaintext,
        cc=cc,
        bcc=bcc,
        email_from=get_dimagi_from_email(),
    )
    log_accounting_info(
        f"Sent subscription renewed email for {context['domain']}"
    )


def send_renewal_reminder_email(subscription, days_left):
    template = 'accounting/email/subscription_renewal_reminder.html'
    template_plaintext = 'accounting/email/subscription_renewal_reminder.txt'
    _send_subscription_ending_reminder_email(subscription, days_left, template, template_plaintext)


def send_subscription_ending_email(subscription, days_left):
    template = 'accounting/email/subscription_ending.html'
    template_plaintext = 'accounting/email/subscription_ending.txt'
    _send_subscription_ending_reminder_email(subscription, days_left, template, template_plaintext)


def _send_subscription_ending_reminder_email(subscription, days_left, template, template_plaintext):
    domain_name = subscription.subscriber.domain
    context = _ending_reminder_context(subscription, days_left)
    subject = context['subject']

    email_html = render_to_string(template, context)
    email_plaintext = render_to_string(template_plaintext, context)

    to, cc, bcc = _get_reminder_email_contacts(subscription, domain_name)
    send_html_email_async.delay(
        subject, to, email_html,
        text_content=email_plaintext,
        cc=cc,
        email_from=get_dimagi_from_email(),
        bcc=bcc,
    )
    log_accounting_info(
        "Sent %(days_left)s-day subscription reminder "
        "email for %(domain)s" % {
            'days_left': days_left,
            'domain': domain_name,
        }
    )


def _get_reminder_email_contacts(subscription, domain):
    from corehq.apps.accounting.models import BillingContactInfo, WebUser

    billing_contacts = set(
        subscription.account.billingcontactinfo.email_list
        if BillingContactInfo.objects.filter(account=subscription.account).exists() else []
    )
    if not billing_contacts:
        from corehq.apps.accounting.views import ManageBillingAccountView
        _soft_assert_contact_emails_missing(
            False,
            'Billing Account for project %s is missing client contact emails: %s' % (
                domain,
                absolute_reverse(ManageBillingAccountView.urlname, args=[subscription.account.id])
            )
        )
    project_admins = {admin.get_email() for admin in WebUser.get_admins_by_domain(domain)}
    dimagi_contacts = {email for email in WebUser.get_dimagi_emails_by_domain(domain)}
    if subscription.account.dimagi_contact:
        dimagi_contacts.add(subscription.account.dimagi_contact)

    to = billing_contacts
    cc = project_admins.difference(billing_contacts)
    bcc = dimagi_contacts.difference(billing_contacts, project_admins)

    if not to:
        to = cc
        cc = None

    return to, cc, bcc


def _ending_reminder_context(subscription, days_left):
    from corehq.apps.domain.views.accounting import DomainSubscriptionView

    if days_left == 1:
        ending_on = _("tomorrow!")
    else:
        ending_on = _("on %s." % subscription.date_end.strftime(USER_DATE_FORMAT))

    domain_name = subscription.subscriber.domain
    plan_name = subscription.plan_version.plan.name
    context = {
        'domain': domain_name,
        'plan_name': plan_name,
        'account': subscription.account.name,
        'ending_on': ending_on,
        'subscription_url': absolute_reverse(
            DomainSubscriptionView.urlname, args=[domain_name]),
        'base_url': get_site_domain(),
        'invoicing_contact_email': settings.INVOICING_CONTACT_EMAIL,
        'sales_email': settings.SALES_EMAIL,
        'plan_info_url': ('https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2420015134/'
                          'CommCare+Pricing+Overview#Detailed-Software-Plan-%26-Feature-Comparisons')
    }

    subject = _(
        "CommCare Alert: %(domain_or_account)s's subscription to "
        "%(plan_name)s ends %(ending_on)s"
    ) % {
        'domain_or_account': (
            subscription.account.name
            if subscription.account.is_customer_billing_account
            else domain_name
        ),
        'plan_name': plan_name,
        'ending_on': ending_on,
    }

    context.update({'subject': subject})
    return context


def send_dimagi_contact_ending_reminder_email(subscription):
    if not subscription.account.dimagi_contact:
        raise SubscriptionReminderError(
            "This subscription has no Dimagi contact."
        )

    subject = _dimagi_ending_reminder_subject(subscription)
    context = _dimagi_ending_reminder_context(subscription)
    email_html = render_to_string('accounting/email/subscription_ending_reminder_dimagi.html', context)
    email_plaintext = render_to_string('accounting/email/subscription_ending_reminder_dimagi.txt', context)
    send_html_email_async.delay(
        subject, subscription.account.dimagi_contact, email_html,
        text_content=email_plaintext,
        email_from=settings.DEFAULT_FROM_EMAIL,
    )


def _dimagi_ending_reminder_subject(subscription):
    if subscription.account.is_customer_billing_account:
        return "CommCare Alert: {account}'s subscriptions are ending on {end_date}".format(
            account=subscription.account.name,
            end_date=subscription.date_end.strftime(USER_DATE_FORMAT))
    else:
        return "CommCare Alert: {domain}'s subscription is ending on {end_date}".format(
            domain=subscription.subscriber.domain,
            end_date=subscription.date_end.strftime(USER_DATE_FORMAT))


def _dimagi_ending_reminder_context(subscription):
    end_date = subscription.date_end.strftime(USER_DATE_FORMAT)
    email = subscription.account.dimagi_contact
    domain = subscription.subscriber.domain
    plan = subscription.plan_version.plan.edition
    context = {
        'plan': plan,
        'end_date': end_date,
        'dimagi_contact': email,
        'accounts_email': settings.ACCOUNTS_EMAIL,
        'base_url': get_site_domain(),
    }
    if subscription.account.is_customer_billing_account:
        account = subscription.account.name
        context.update({
            'account_or_domain': account,
            'is_customer_account': True,
        })
    else:
        context.update({
            'account_or_domain': domain,
            'is_customer_account': False,
        })
    return context
