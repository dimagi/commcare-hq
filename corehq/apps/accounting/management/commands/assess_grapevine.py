import csv
from datetime import datetime

from dateutil.relativedelta import relativedelta

from django.core.management import BaseCommand
from django.db.models import Sum

from corehq.apps.smsbillables.models import SmsBillable, SmsGatewayFeeCriteria
from corehq.const import SERVER_DATETIME_FORMAT
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

        start_date = correct_billables.earliest('date_sent').date_sent
        end_date = correct_billables.latest('date_sent').date_sent

        print start_date
        print end_date

        domain_and_month_to_data = {_['domain']: {} for _ in correct_billables.values('domain').distinct()}

        for (year, month) in with_progress_bar(list(get_months_in_range(end_date, start_date))):
            for domain in domain_and_month_to_data:
                billables_this_month = correct_billables.filter(
                    domain=domain,
                    date_sent__year=year,
                    date_sent__month=month,
                )
                bad_billables_this_month = bad_billables.filter(
                    domain=domain,
                    date_sent__year=year,
                    date_sent__month=month,
                )
                billable_count = billables_this_month.count()
                correct_total_gateway_cost = billables_this_month.aggregate(Sum('gateway_fee__amount'))['gateway_fee__amount__sum'] or 0
                bad_total_gateway_cost = bad_billables_this_month.aggregate(Sum('gateway_fee__amount'))['gateway_fee__amount__sum'] or 0
                domain_and_month_to_data[domain][(year, month)] = {
                    'number_of_smsbillables': billable_count,
                    'correct_total_gateway_cost': correct_total_gateway_cost,
                    'bad_total_gateway_cost': bad_total_gateway_cost,
                    'under_billing': correct_total_gateway_cost - bad_total_gateway_cost,
                }
        print domain_and_month_to_data

        filename = 'assess_grapevine-%s.csv' % datetime.utcnow().strftime(SERVER_DATETIME_FORMAT)
        with open(filename, 'w') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Project', 'Year', 'Month',
                'Number of SMS Billables', 'Total correct gateway cost', 'Total incorrect gateway cost',
                'Amount underbilled'
            ])
            for domain in sorted(domain_and_month_to_data):
                for (year, month) in sorted(domain_and_month_to_data[domain]):
                    data = domain_and_month_to_data[domain][(year, month)]
                    writer.writerow([
                        domain.encode('utf-8'), year, month, data['number_of_smsbillables'],
                        data['correct_total_gateway_cost'], data['bad_total_gateway_cost'], data['under_billing']
                    ])


# https://stackoverflow.com/questions/4039879/best-way-to-find-the-months-between-two-dates
def diff_month(d1, d2):
    return (d1.year - d2.year) * 12 + d1.month - d2.month


def get_months_in_range(d1, d2):
    months_diff = diff_month(d1, d2)

    for i in range(months_diff + 1):
        next_date = d2 + relativedelta(months=i)
        yield (next_date.year, next_date.month)
        return

