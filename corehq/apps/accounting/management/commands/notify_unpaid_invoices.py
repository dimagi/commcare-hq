import datetime
from django.core.management import BaseCommand
from django.core.management import CommandError
from django.template.loader import render_to_string
from django.utils.translation import ugettext

import settings
from corehq.apps.accounting.models import Invoice, SoftwarePlanEdition, SubscriptionType, DefaultProductPlan
from corehq.apps.accounting.utils import get_dimagi_from_email
from corehq.apps.domain.views import DomainSubscriptionView
from corehq.apps.domain.views import DomainBillingStatementsView
from corehq.util.view_utils import absolute_reverse
from corehq.apps.hqwebapp.tasks import send_html_email_async


class Command(BaseCommand):
    help = 'Sends subscription downgrade warnings for unpaid invoices'

    def handle(self, *args, **options):
        print "Restoring ES indices from snapshot"
        if len(args) != 0:
            raise CommandError('Usage is ./manage.py notify_unpaid_invoices %s' % self.args)
        today = datetime.date.today()
        invoices = Invoice.objects.filter(is_hidden=False,
                                          subscription__service_type=SubscriptionType.PRODUCT,
                                          date_paid__isnull=True,
                                          date_due__lt=today)\
            .exclude(subscription__plan_version__plan__edition=SoftwarePlanEdition.ENTERPRISE)\
            .order_by('date_due')\
            .select_related('subscription__subscriber')

        domains = set()
        for invoice in invoices:
            if invoice.get_domain() not in domains:
                domains.add(invoice.get_domain())
                domain_invoices = Invoice.objects.filter(is_hidden=False,
                                                         subscription__subscriber__domain=invoice.get_domain())\
                    .prefetch_related('subscription')
                total = sum(i.balance for i in domain_invoices)
                manual_downgrade = any(sub.manual_downgrade for sub in domain_invoices.subscription)
                if total >= 100 and not manual_downgrade:
                    days_ago = (today - invoice.date_due).days
                    context = {
                        'invoice': invoice,
                        'total': total,
                        'subscription_url': absolute_reverse(DomainSubscriptionView.urlname,
                                                             args=[invoice.get_domain()]),
                        'statements_url': absolute_reverse(DomainBillingStatementsView.urlname,
                                                           args=[invoice.get_domain()]),
                        'date_60': invoice.date_due + datetime.timedelta(days=60),
                        'contact_email': settings.INVOICING_CONTACT_EMAIL
                    }
                    if days_ago == 61:
                        _downgrade_domain(invoice)
                        _send_downgrade_notice(invoice, context)
                    elif days_ago == 58:
                        _send_downgrade_warning(invoice, context)
                    elif days_ago == 30:
                        _send_overdue_notice(invoice, context)
                    elif days_ago == 1:
                        _create_overdue_notification(invoice, context)


def _send_downgrade_notice(invoice, context):
    send_html_email_async.delay(
        ugettext('Oh no! Your CommCare subscription for {} has been downgraded'.format(invoice.get_domain())),
        invoice.contact_emails,
        render_to_string('accounting/downgrade.html', context),
        render_to_string('accounting/downgrade.txt', context),
        cc=[settings.ACCOUNTS_EMAIL],
        email_from=get_dimagi_from_email()
    )


def _downgrade_domain(invoice):
    invoice.subscription.change_plan(
        DefaultProductPlan.get_default_plan_version(
            SoftwarePlanEdition.COMMUNITY
        ),
        note='Automatic downgrade to community for invoice 60 days late'
    )


def _send_downgrade_warning(invoice, context):
    send_html_email_async.delay(
        ugettext("CommCare Alert: {}'s subscription will be downgraded to Community Plan after tomorrow!".format(
            invoice.get_domain()
        )),
        invoice.contact_emails,
        render_to_string('accounting/downgrade_warning.html', context),
        render_to_string('accounting/downgrade_warning.txt', context),
        cc=[settings.ACCOUNTS_EMAIL],
        email_from=get_dimagi_from_email())


def _send_overdue_notice(invoice, context):
    send_html_email_async.delay(
        ugettext('CommCare Billing Statement 30 days Overdue for {}'.format(invoice.get_domain())),
        invoice.contact_emails,
        render_to_string('accounting/30_days.html', context),
        render_to_string('accounting/30_days.txt', context),
        cc=[settings.ACCOUNTS_EMAIL],
        email_from=get_dimagi_from_email())


def _create_overdue_notification(invoice, context):
    message = ugettext('Reminder - your {} statement is past due!'.format(
        invoice.date_start.strftime('%B')
    ))
    note = Notification.objects.create(content=message, url=context['statements_url'],
                                       domain_specific=True, type='billing',
                                       domains=[invoice.get_domain()])
    note.activate()
