from datetime import date, datetime, timedelta

from django.core.management import BaseCommand

from corehq.apps.accounting.invoicing import should_create_invoice
from corehq.apps.accounting.models import Subscription
from corehq.apps.smsbillables.models import SmsBillable


class Command(BaseCommand):

    def handle(self, **options):
        affected_date_ranges = [
            [date(2018, 6, 1), date(2018, 6, 30)],
            [date(2018, 7, 1), date(2018, 7, 31)],
            [date(2018, 8, 1), date(2018, 8, 31)]
        ]

        for month_start, month_end in affected_date_ranges:
            for affected_subcription in Subscription.visible_objects.filter(
                date_start=month_end,
            ):
                if should_create_invoice(
                    affected_subcription, affected_subcription.subscriber.domain,
                    month_start, month_end
                ):
                    print affected_subcription
                    print sum(
                        b.gateway_charge + b.usage_charge
                        for b in SmsBillable.objects.filter(
                            domain=affected_subcription.subscriber.domain,
                            date_sent__gte=month_end,
                            date_sent__lt=datetime.combine(month_end, datetime.min.time()) + timedelta(days=1)
                        )
                    )
                    print '----------'
