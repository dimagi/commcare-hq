from dateutil.relativedelta import relativedelta

from django.core.management import BaseCommand
from django.db.models import Sum

from corehq.apps.smsbillables.models import SmsBillable, SmsGatewayFeeCriteria


class Command(BaseCommand):

    def handle(self, *args, **options):
        inactive_criteria = SmsGatewayFeeCriteria.objects.filter(is_active=False)
        assert inactive_criteria.count() == 2
        bad_billables = SmsBillable.objects.filter(gateway_fee__criteria__is_active=False)
        log_ids = bad_billables.values('log_id')
        correct_billables = SmsBillable.objects.filter(is_valid=True, log_id__in=log_ids)
        assert bad_billables.count() == correct_billables.count()
        assert correct_billables.count() == correct_billables.filter(gateway_fee__criteria__is_active=True).count()

        bad_billable_total_gateway_cost = bad_billables.aggregate(Sum('gateway_fee__amount'))
        correct_billable_total_gateway_cost = correct_billables.aggregate(Sum('gateway_fee__amount'))

        start_date = correct_billables.earliest('date_sent')
        end_date = correct_billables.latest('date_sent')

        for (year, month) in get_months_in_range(start_date, end_date):
            domains_in_month = correct_billables.values('domain').distinct()
            print domains_in_month
            for domain in (domains_in_month):
                print "%s %d-%d" % (domain, year, month)



# https://stackoverflow.com/questions/4039879/best-way-to-find-the-months-between-two-dates
def diff_month(d1, d2):
    return (d1.year - d2.year) * 12 + d1.month - d2.month


def get_months_in_range(d1, d2):
    months_diff = diff_month(d1, d2)

    yield (d2.year, d2.month)
    for i in range(months_diff):
        next_date = d2 + relativedelta(months=i)
        yield (next_date.year, next_date.month)

