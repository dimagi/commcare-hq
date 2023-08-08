from decimal import Decimal

from django.core.management import BaseCommand

from corehq.apps.accounting.models import BillingAccount
from corehq.apps.smsbillables.models import SmsBillable


class Command(BaseCommand):
    help = """Debugs SMS Invoicing Issue"""

    def handle(self, **options):
        account = BillingAccount.objects.get(id=35480)
        self.stdout.write(f"Checking SMS costs for {account.name}...")

        total_cost = Decimal('0.00')
        active_account_domains = set(account.subscription_set.filter(
            is_active=True).values_list('subscriber__domain', flat=True))

        relevant_sms_billables = SmsBillable.objects.filter(domain__in=active_account_domains)
        for billable in relevant_sms_billables:
            total_message_charge = billable.gateway_charge + billable.usage_charge
            total_cost += total_message_charge
