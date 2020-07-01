import dateutil
from dateutil.relativedelta import relativedelta

from django.core.management.base import BaseCommand
from custom.icds_reports.tasks import _get_monthly_dates, update_service_delivery_report
from dimagi.utils.dates import force_to_date


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'start_month'
        )
        parser.add_argument(
            'end_month'
        )

    def handle(self, start_month, end_month, *args, **options):
        start_month = force_to_date(start_month).replace(day=1)
        end_month = force_to_date(end_month).replace(day=1)

        while start_month <= end_month:
            month_string = start_month.strftime("%Y-%m-%d")
            print("Starting data filling for {}".format(month_string))
            update_service_delivery_report(month_string)
            print("Completed data filling for {}".format(month_string))
            start_month = start_month + relativedelta(months=1)
