import datetime
from decimal import Decimal
from sys import stdout
from corehq.apps.accounting.models import (
    Currency,
    BillingAccount,
    CreditLine,
    CreditAdjustmentReason
)
from corehq.apps.smsbillables.models import SmsBillable
from django.core.management import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Fix conversion issue for INR-based smsbillables on india server created' \
           'prior to 3/1/2016'

    def handle(self, *args, **options):
        if raw_input(
            'Are you sure you want to re-bill all SMS billables with'
            ' gateway fees in INR calculated prior to March 1, 2016?\n'
            'This action will invalidate the old billables, create new ones,'
            ' and add the difference as general account credit to each'
            ' affected domain. \n[y/n]'
        ).lower() != 'y':
            raise CommandError('abort')

        inr = Currency.objects.filter(code="INR").first()

        affected_criteria = SmsBillable.objects.filter(
            gateway_fee__currency__code=inr.code,
            date_created__lt=datetime.date(2016, 3, 1),
            is_valid=True
        )
        for unique_b in affected_criteria.order_by('domain').distinct('domain'):
            all_affected_billables = affected_criteria.filter(
                domain=unique_b.domain,
            )
            total_affected = all_affected_billables.count()
            if total_affected > 0:
                print(
                    "\nUpdating {total_affected} billables for"
                    " domain {domain}".format(
                        domain=unique_b.domain,
                        total_affected=total_affected
                    )
                )
                stdout.write(">> BILLABLES: ")
            total_diff = Decimal('0.0')
            for billable in all_affected_billables.all():
                stdout.write('.')
                updated_billable = self._get_updated_billable(billable, inr)

                old_gateway_cost = (
                    billable.gateway_fee.amount /
                    billable.gateway_fee_conversion_rate
                )
                new_gateway_cost = (
                    updated_billable.gateway_fee.amount /
                    updated_billable.gateway_fee_conversion_rate
                )

                difference = old_gateway_cost - new_gateway_cost
                total_diff += difference * Decimal('1.0000')
                total_diff += difference * Decimal('1.0000')
            stdout.flush()
            if total_diff > Decimal('0.0'):
                print(
                    "\n!! >>> FOUND difference of {diff}, "
                    "applying General Credits to domain {domain}".format(
                        diff=round(total_diff, 4),
                        domain=unique_b.domain,
                    )
                )
                try:
                    affected_account = BillingAccount.get_account_by_domain(unique_b.domain)
                    CreditLine.add_credit(
                        total_diff,
                        affected_account,
                        note="Automated re-calc for UNICEL SMS Fees due to incorrect"
                             "conversion rate",
                        reason=CreditAdjustmentReason.MANUAL,
                    )
                    for b in all_affected_billables.all():
                        b.is_valid = False
                        b.save()
                except Exception as e:
                    print("Could not add credits to {domain} due to {error}".format(
                        domain=unique_b.domain,
                        error=e
                    ))

    def _get_updated_billable(self, old_billable, updated_currency):
        new_billable = SmsBillable(
            log_id=old_billable.log_id,
            phone_number=old_billable.phone_number,
            direction=old_billable.direction,
            date_sent=old_billable.date_sent,
            domain=old_billable.domain,
            multipart_count=old_billable.multipart_count
        )
        new_billable.gateway_fee = old_billable.gateway_fee
        new_billable.gateway_fee_conversion_rate = updated_currency.rate_to_default
        new_billable.usage_fee = old_billable.usage_fee
        new_billable.save()
        return new_billable
