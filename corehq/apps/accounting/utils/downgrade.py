from django.conf import settings
from django.template.loader import render_to_string

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.hqwebapp.tasks import send_html_email_async

from corehq.apps.accounting.utils import (
    get_dimagi_from_email,
)


def is_subscription_eligible_for_downgrade_process(subscription):
    return (
        subscription.plan_version.plan.edition not in [
            SoftwarePlanEdition.COMMUNITY,
            SoftwarePlanEdition.PAUSED,
        ] and not subscription.skip_auto_downgrade
    )


def send_downgrade_notice(invoice, context):
    send_html_email_async.delay(
        _('Oh no! Your CommCare subscription for {} has been paused'.format(invoice.get_domain())),
        invoice.contact_emails,
        render_to_string('accounting/email/downgrade.html', context),
        render_to_string('accounting/email/downgrade.txt', context),
        cc=[settings.ACCOUNTS_EMAIL],
        bcc=[settings.GROWTH_EMAIL],
        email_from=get_dimagi_from_email()
    )
