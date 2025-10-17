from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef

from corehq.apps.accounting.models import (
    BillingAccount,
    InvoicingPlan,
    SoftwarePlanEdition,
    Subscription,
    SubscriptionType,
)


class Command(BaseCommand):
    help = (
        'List BillingAccounts who need to ba evaluated for autopay setup.'
    )

    def handle(self, *args, **options):
        active_monthly_subs = Subscription.visible_objects.filter(
            is_active=True,
            do_not_invoice=False,
            auto_generate_credits=False,
            is_hidden_to_ops=False,
            service_type__in=[SubscriptionType.PRODUCT, SubscriptionType.IMPLEMENTATION],
            account=OuterRef('pk'),
            plan_version__plan__is_annual_plan=False,
            plan_version__plan__edition__in=[
                SoftwarePlanEdition.STANDARD,
                SoftwarePlanEdition.PRO,
                SoftwarePlanEdition.ADVANCED,
                SoftwarePlanEdition.ENTERPRISE,
            ],
        )
        accounts = (
            BillingAccount.objects.filter(
                auto_pay_user__isnull=True,
                is_active=True,
                invoicing_plan=InvoicingPlan.MONTHLY,
            )
            .annotate(has_active_monthly=Exists(active_monthly_subs))
            .filter(has_active_monthly=True)
            .select_related('billingcontactinfo')
        )

        for acc in accounts.iterator():
            emails = ', '.join(getattr(getattr(acc, 'billingcontactinfo', None), 'email_list', []) or [])
            active_subs = acc.subscription_set.filter(is_active=True)
            self.stdout.write(
                f'{acc.id}\t{acc.name}\t{emails}\t{acc.entry_point}'
                f'\t{active_subs.count()}\t{acc.created_by_domain}'
            )
