import datetime
import io
from decimal import Decimal

from django.conf import settings
from django.template.loader import render_to_string

from corehq.apps.accounting.models import Subscription, CreditLine
from corehq.apps.accounting.utils import quantize_accounting_decimal
from corehq.util.log import send_HTML_email
from couchexport.export import export_from_tables
from couchexport.models import Format


class CreditsAutomatedReport(object):
    """
    This report gets sent to the finance team to determine how many credits
    are still active on subscriptions and billing accounts on HQ.

    But why base the report on 'yesterday'?
    It is much more difficult to trigger a report on the last day of the month
    (which changes) vs. the first day of the month.
    Since this report is generally run of the first hour on the first day
    of the month, the report is really about the previous day's credits.
    """

    def send_report(self, recipient):
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        yesterday_string = yesterday.strftime("%d %b %Y")
        table = self._generate_report_table()

        file_to_attach = io.BytesIO()
        export_from_tables(
            [[yesterday_string, table]],
            file_to_attach,
            Format.XLS_2007
        )

        email_context = {
            'date_of_report': yesterday_string,
        }
        email_content = render_to_string(
            'accounting/email/credits_on_hq.html', email_context)
        email_content_plaintext = render_to_string(
            'accounting/email/credits_on_hq.txt', email_context)
        format_dict = Format.FORMAT_DICT[Format.XLS_2007]

        file_attachment = {
            'title': 'Credits_on_hq_{}_{}'.format(
                yesterday.isoformat(),
                settings.SERVER_ENVIRONMENT,
            ),
            'mimetype': format_dict['mimetype'],
            'file_obj': file_to_attach,
        }

        from_email = "Dimagi Finance <{}>".format(settings.DEFAULT_FROM_EMAIL)
        send_HTML_email(
            "{} Credits on HQ {}".format(
                yesterday_string,
                settings.SERVER_ENVIRONMENT,
            ),
            recipient,
            email_content,
            email_from=from_email,
            text_content=email_content_plaintext,
            file_attachments=[file_attachment],
        )

    def _generate_report_table(self):
        table = [[
            "Project",
            "Edition",
            "General Credits / Credits Remaining for Subscription",
            "Feature / Product Credits for Subscription",
            "Account Name",
            "Billing Account-level Credits",
            "Billing Account-level Feature / Product Credits",
            "Product/Implementation?",
        ]]

        for subscription in Subscription.visible_and_suppressed_objects.filter(
                is_active=True):
            domain = subscription.subscriber.domain
            plan_edition = subscription.plan_version.plan.edition
            credit_info = self._get_credit_info(subscription)

            general_credit = (credit_info['general_credit']['amount']
                              if credit_info['general_credit']
                              else "")

            feature_credit = (credit_info['feature_credit']['amount']
                              if credit_info['feature_credit']
                              else "")

            account_credit = (credit_info['account_general_credit']['amount']
                              if credit_info['account_general_credit']['amount']
                              else "")

            account_feature_credit = (credit_info['account_feature_credit']['amount']
                              if credit_info['account_feature_credit']['amount']
                              else "")

            if not (general_credit in ["", "0.00"]) or not (account_credit in ["", "0.00"]):
                table.append([
                    domain,
                    plan_edition,
                    general_credit,
                    feature_credit,
                    subscription.account.name if subscription.account else "",
                    account_credit,
                    account_feature_credit,
                    subscription.service_type,
                ])

        return table

    def _get_credit_info(self, subscription):
        return {
            'general_credit': self._fmt_credit(self._credit_grand_total(
                CreditLine.get_credits_by_subscription_and_features(
                    subscription
                )
            )),
            'feature_credit': self._fmt_credit(self._credit_grand_total(
                CreditLine.get_non_general_credits_by_subscription(subscription)
            )),
            'account_general_credit': self._fmt_credit(self._credit_grand_total(
                CreditLine.get_credits_for_account(
                    subscription.account
                ) if subscription.account else None
            )),
            'account_feature_credit': self._fmt_credit(self._credit_grand_total(
                CreditLine.get_non_general_credits_for_account(subscription.account)
            )),
        }

    @staticmethod
    def _credit_grand_total(credit_lines):
        return sum([c.balance for c in credit_lines]) if credit_lines else Decimal('0.00')

    @staticmethod
    def _fmt_credit(credit_amount=None):
        if credit_amount is None:
            return {
                'amount': "--",
            }
        return {
            'amount': quantize_accounting_decimal(credit_amount),
            'is_visible': credit_amount != Decimal('0.0'),
        }
