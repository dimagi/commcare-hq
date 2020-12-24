import datetime

from django.core.management.base import BaseCommand

from corehq.apps.sms.models import SMS
from corehq.apps.smsbillables.models import SmsBillable


class Command(BaseCommand):
    help = ""

    def _get_stats(self, date_start, date_stop=None):
        query = SMS.objects.filter(
            date__gte=date_start,
            backend_api='TWILIO'
        )
        if date_stop:
            query = query.filter(date__lt=date_stop)
        print(f"Found {query.count()} messages")
        available_ids = list(query.values_list('couch_id', flat=True))
        total_billed = SmsBillable.objects.filter(log_id__in=available_ids).count()
        total_bad = len(available_ids) - total_billed
        print(f"Total billed sms: {total_billed}")
        print(f"Total un-billed sms: {total_bad}")

    def handle(self, **options):
        october_first = datetime.datetime(2020, 10, 1)
        november_first = datetime.datetime(2020, 11, 1)
        december_first = datetime.datetime(2020, 12, 1)

        print("\n\nData for OCTOBER")
        self._get_stats(october_first, november_first)

        print("\n\nData for NOVEMBER")
        self._get_stats(november_first, december_first)

        print("\n\nData for DECEMBER")
        self._get_stats(december_first)
