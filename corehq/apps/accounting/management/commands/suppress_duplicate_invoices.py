from django.core.management.base import BaseCommand
from django.db.models import Count
from corehq.apps.accounting.interface import get_subtotal_and_deduction
from corehq.apps.accounting.models import Invoice, CreditLine, FeatureType
from corehq.util.dates import get_first_last_days


class Command(BaseCommand):
    help = 'Put credit back for duplicate invoices and suppress them'

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
        dry_run_tag = '[DRY_RUN]' if dry_run else ''


        start_date, end_date = get_first_last_days(year, month)

        # Filter the Invoice objects based on the date_start
        invoices_of_given_date = Invoice.objects.filter(date_start__range=(start_date, end_date),
                                                        is_hidden_to_ops=False)

        # Extract the subscription ids that have duplicate invoices
        duplicate_subs_ids = invoices_of_given_date.values('subscription').annotate(
            count=Count('id')).filter(count__gt=1).values_list('subscription', flat=True)

        suppressed_count = 0
        for sub_id in duplicate_subs_ids:
            related_invoices = list(Invoice.objects.filter(
                subscription_id=sub_id, date_start__range=(start_date, end_date)).order_by('-date_created'))
            first_created_invoice_id = related_invoices[0].id
            for invoice in related_invoices[:-1]:
                custom_note = f"{note}. Referenced to invoice {first_created_invoice_id}."
                if invoice.balance != invoice.subtotal:
                    # credit them back
                    self.revert_invoice_payment(invoice, custom_note, dry_run)
                # suppress invoice
                print(f'{dry_run_tag}Suppressing invoice {invoice.id} for domain'
                      f'{invoice.subscription.subscriber.domain} ', end='')
                if not dry_run:
                    invoice.is_hidden_to_ops = True
                    invoice.save()
                suppressed_count += 1
                print("✓")

        self.stdout.write(self.style.SUCCESS(f'{dry_run_tag}Successfully suppressed {suppressed_count} '
                                             f'duplicate invoices for Statement Period: {year}-{month}'))

    def revert_invoice_payment(self, invoice, note, dry_run=False):
        dry_run_tag = '[DRY_RUN]' if dry_run else ''

        print(f'{dry_run_tag}Reverting payment for Invoice Id: {invoice.id}, '
              f'Domain: {invoice.subscription.subscriber.domain}')
        # Total Credit
        payment_by_credit = -invoice.applied_credit

        plan_subtotal, plan_deduction = get_subtotal_and_deduction(
            invoice.lineitem_set.get_products().all()
        )
        if plan_deduction:
            print(f'{dry_run_tag}Adding plan credit: {plan_deduction}')
            if not dry_run:
                CreditLine.add_credit(amount=plan_deduction, subscription=invoice.subscription,
                                    is_product=True, note=note)
            payment_by_credit -= plan_deduction

        for feature in FeatureType.CHOICES:
            feature_subtotal, feature_deduction = get_subtotal_and_deduction(
                invoice.lineitem_set.get_feature_by_type(feature).all()
            )
            if feature_deduction:
                print(f"{dry_run_tag}Adding {feature[0]} credit: {feature_deduction}")
                if not dry_run:
                    CreditLine.add_credit(amount=feature_deduction, subscription=invoice.subscription,
                                        feature_type=feature[0], note=note)
                payment_by_credit -= feature_deduction

        # After deducting plan credit and feature credit, the remained credit should be type Any
        if payment_by_credit:
            print(f"{dry_run_tag}Adding remaining credit (type Any): {payment_by_credit}")
            if not dry_run:
                CreditLine.add_credit(amount=payment_by_credit, subscription=invoice.subscription, note=note)

        # Calculate the amount paid not by credit
        payment_by_other = invoice.subtotal + invoice.applied_credit - invoice.balance
        if payment_by_other:
            print(f"{dry_run_tag}Adding credit for other payments: {payment_by_other}")
            if not dry_run:
                CreditLine.add_credit(amount=payment_by_other, subscription=invoice.subscription, note=note)
