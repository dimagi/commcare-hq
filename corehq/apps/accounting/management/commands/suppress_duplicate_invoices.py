import csv
import datetime
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db.models import Count
from corehq.apps.accounting.interface import get_subtotal_and_deduction
from corehq.apps.accounting.models import (BillingRecord, CreditAdjustment, Invoice,
                                           CreditLine, FeatureType, LineItem)
from corehq.util.dates import get_first_last_days
from dimagi.utils.dates import add_months


class Command(BaseCommand):
    help = 'Put credit back for duplicate invoices and suppress them, and generate a report'

    def add_arguments(self, parser):
        parser.add_argument('year', type=int, help='The year of the statement period.')
        parser.add_argument('month', type=int, help='The month of the statement period.')
        parser.add_argument('note', type=str,
                            help='A note to be added when crediting back the amount')
        parser.add_argument('--dry-run', action='store_true', default=False)

    def handle(self, *args, **kwargs):
        year = kwargs['year']
        month = kwargs['month']
        note = kwargs['note']
        dry_run = kwargs['dry_run']
        dry_run_tag = '[DRY_RUN] ' if dry_run else ''

        start_date, end_date = get_first_last_days(year, month)

        # Filter the Invoice objects based on the date_start
        invoices_of_given_date = Invoice.objects.filter(date_start__range=(start_date, end_date),
                                                        is_hidden_to_ops=False)

        # Extract the subscription ids that have duplicate invoices
        duplicate_subs_ids = invoices_of_given_date.values('subscription').annotate(
            count=Count('id')).filter(count__gt=1).values_list('subscription', flat=True)

        suppressed_count = 0

        file_path = "/tmp/duplicate_invoices.csv"
        with open(file_path, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            headers = ['Invoice ID', 'BillingAccount Name', 'Dimagi Contact', 'Domain', 'Software Plan Name',
                       'Service Type', 'Subscription Id', 'tax_rate', 'balance', 'date_due', 'date_paid',
                       'date_created', 'date_start', 'date_end', 'is_hidden', 'is_hidden_to_ops', 'last_modified',
                       'Emailed To List', 'Plan Cost', 'Plan Credit', 'SMS Cost', 'SMS Credit', 'User Cost',
                       'User Credit', 'Total Cost', 'Total Credit', 'Will Suppress', 'Will Revert',
                       'Suppression Status', 'Revert Status']
            csvwriter.writerow(headers)
            for sub_id in duplicate_subs_ids:
                related_invoices = list(Invoice.objects.filter(is_hidden_to_ops=False,
                    subscription_id=sub_id, date_start__range=(start_date, end_date)).order_by('date_created'))
                first_created_invoice_id = related_invoices[0].id
                row_data = self.get_csv_row_data(related_invoices[0], False, False, "", "")
                csvwriter.writerow(row_data)
                for invoice in related_invoices[1:]:
                    will_suppress = True
                    suppression_status = ""
                    custom_note = f"{note}. Referenced to invoice {first_created_invoice_id}."
                    # credit back the paid amount
                    will_revert, revert_status = self.revert_invoice_payment(
                        invoice, custom_note, year, month, dry_run)
                    # suppress invoice
                    print(f'{dry_run_tag}Suppressing invoice {invoice.id} for domain '
                        f'{invoice.subscription.subscriber.domain} ', end='')
                    if not dry_run:
                        invoice.is_hidden_to_ops = True
                        invoice.save()
                        suppression_status = True
                    row_data = self.get_csv_row_data(
                        invoice, will_suppress, will_revert, suppression_status, revert_status)
                    csvwriter.writerow(row_data)
                    suppressed_count += 1
                    print("✓")

        self.stdout.write(self.style.SUCCESS(f'{dry_run_tag}Successfully suppressed {suppressed_count} '
                                             f'duplicate invoices for Statement Period: {year}-{month}'))

    def revert_invoice_payment(self, invoice, note, year, month, dry_run=False):
        dry_run_tag = '[DRY_RUN] ' if dry_run else ''
        payment_by_other = invoice.subtotal
        will_revert = False
        reverted = ""

        # Plan Credit
        if not invoice.subscription.auto_generate_credits:
            plan_subtotal, plan_deduction = get_subtotal_and_deduction(
                invoice.lineitem_set.get_products().all()
            )
            plan_credit = -plan_deduction
            if plan_credit:
                will_revert = True
                print(f'{dry_run_tag}Adding plan credit: {plan_credit} to '
                    f'domain {invoice.subscription.subscriber.domain}')
                if not dry_run:
                    CreditLine.add_credit(amount=plan_credit, subscription=invoice.subscription,
                                        is_product=True, note=note)
                    reverted = True
        else:
            # Check if we generate duplicate product credit line
            # We don't need to return those auto-generated credits
            current_year, current_month = add_months(year, month, 1)

            date_start = datetime.datetime(current_year, current_month, 1)
            date_end = date_start + timedelta(days=1) - timedelta(seconds=1)
            try:
                CreditLine.objects.get(account=invoice.subscription.account,
                                       subscription=invoice.subscription, is_product=True, is_active=True)
            except CreditLine.MultipleObjectsReturned:
                print(f"{dry_run_tag}Multiple plan credit lines found for subscription"
                      f" {invoice.subscription.plan_version.plan.name}.")
                duplicate_cl = CreditLine.objects.filter(account=invoice.subscription.account,
                                                         subscription=invoice.subscription, is_product=True,
                                                         is_active=True,
                                                         date_created__range=(date_start, date_end)).first()
                if not dry_run:
                    CreditAdjustment.objects.filter(credit_line=duplicate_cl).delete()
                    duplicate_cl.delete()
                    print("Duplicate Plan Credit Line deleted")

        # Feature Credit
        for feature in FeatureType.CHOICES:
            feature_subtotal, feature_deduction = get_subtotal_and_deduction(
                invoice.lineitem_set.get_feature_by_type(feature[0]).all()
            )
            feature_credit = -feature_deduction
            if feature_credit:
                will_revert = True
                print(f"{dry_run_tag}Adding {feature[0]} credit: {feature_credit} to "
                      f"domain {invoice.subscription.subscriber.domain}")
                if not dry_run:
                    CreditLine.add_credit(amount=feature_credit, subscription=invoice.subscription,
                                        feature_type=feature[0], note=note)
                    reverted = True

        # Any Credit
        any_credit = -invoice.applied_credit
        if any_credit:
            will_revert = True
            payment_by_other -= any_credit
            print(f"{dry_run_tag}Adding type Any credit: {any_credit} to "
                  f"domain {invoice.subscription.subscriber.domain}")
            if not dry_run:
                CreditLine.add_credit(amount=any_credit, subscription=invoice.subscription, note=note)
                reverted = True

        # Calculate the amount paid not by credit
        payment_by_other -= invoice.balance
        if payment_by_other:
            will_revert = True
            print(f"{dry_run_tag}Adding credit for other payments: {payment_by_other} "
                  f"to domain {invoice.subscription.subscriber.domain}")
            if not dry_run:
                CreditLine.add_credit(amount=payment_by_other, subscription=invoice.subscription, note=note)
                reverted = True

        if will_revert:
            print(f'{dry_run_tag}Successfully reverted payment for Invoice Id: {invoice.id}, '
              f'Domain: {invoice.subscription.subscriber.domain}')
        return will_revert, reverted

    def get_csv_row_data(self, invoice, will_suppress, will_revert, suppresion_status, revert_status):
        billing_record = BillingRecord.objects.filter(invoice=invoice,
                                                      date_created__gt=invoice.date_end).first() or None
        emailed_to_combined = "; ".join(billing_record.emailed_to_list) if billing_record else ""

        related_line_items = LineItem.objects.filter(subscription_invoice=invoice)

        # Compute the subtotals and credits for the three categories
        plan_subtotal, plan_credit = get_subtotal_and_deduction(
            [item for item in related_line_items if item.product_rate])

        sms_line_items = [item for item in related_line_items
                          if item.feature_rate and item.feature_rate.feature.feature_type == FeatureType.SMS]
        user_line_items = [item for item in related_line_items
                           if item.feature_rate and item.feature_rate.feature.feature_type == FeatureType.USER]

        sms_subtotal, sms_credit = get_subtotal_and_deduction(sms_line_items)
        user_subtotal, user_credit = get_subtotal_and_deduction(user_line_items)
        row_data = [
            invoice.id,
            invoice.subscription.account.name,
            invoice.subscription.account.dimagi_contact,
            invoice.subscription.subscriber.domain,
            invoice.subscription.plan_version.plan.name,
            invoice.subscription.service_type,
            invoice.subscription_id,
            invoice.tax_rate,
            invoice.balance,
            invoice.date_due,
            invoice.date_paid,
            invoice.date_created,
            invoice.date_start,
            invoice.date_end,
            invoice.is_hidden,
            invoice.is_hidden_to_ops,
            invoice.last_modified,
            emailed_to_combined,
            plan_subtotal, plan_credit,
            sms_subtotal, sms_credit,
            user_subtotal, user_credit,
            invoice.subtotal,
            invoice.applied_credit
        ]
        row_data.extend([will_suppress, will_revert, suppresion_status, revert_status])
        return row_data
