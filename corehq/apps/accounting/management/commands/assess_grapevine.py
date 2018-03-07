from dateutil.relativedelta import relativedelta

from django.core.management import BaseCommand
from django.db.models import Sum

from corehq.apps.smsbillables.models import SmsBillable, SmsGatewayFeeCriteria
from corehq.util.log import with_progress_bar


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

        start_date = correct_billables.earliest('date_sent').date_sent
        end_date = correct_billables.latest('date_sent').date_sent

        print start_date
        print end_date

        domain_and_month_to_data = {}

        for (year, month) in with_progress_bar(list(get_months_in_range(end_date, start_date))):
            domains_in_month = correct_billables.values('domain').distinct()
            for domain in domains_in_month:
                domain = domain['domain']
                domain_and_month_to_data.setdefault(domain, {})
                domain_and_month_to_data[domain][(year, month)] = {
                    'number_of_smsbillables': correct_billables.filter(
                        domain=domain,
                        date_sent__year=year,
                        date_sent__month=month,
                    ).count()
                }
        print domain_and_month_to_data


# https://stackoverflow.com/questions/4039879/best-way-to-find-the-months-between-two-dates
def diff_month(d1, d2):
    return (d1.year - d2.year) * 12 + d1.month - d2.month


def get_months_in_range(d1, d2):
    months_diff = diff_month(d1, d2)

    for i in range(months_diff + 1):
        next_date = d2 + relativedelta(months=i)
        yield (next_date.year, next_date.month)
        return

