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
        print("These messages all do not have billables:")
        total_bad = 0
        for sms in query.all():
            if not SmsBillable.objects.filter(log_id=sms.couch_id).exists():
                print(sms.couch_id)
                total_bad += 1
        print("-------")
        print(f"Total un-billed sms: {total_bad}")

    def handle(self, domains, **options):
        october_first = datetime.datetime(2020, 10, 1)
        november_first = datetime.datetime(2020, 11, 1)
        december_first = datetime.datetime(2020, 12, 1)

        print("\n\nData for OCTOBER")
        self._get_stats(october_first, november_first)

        print("\n\nData for NOVEMBER")
        self._get_stats(november_first, december_first)

        print("\n\nData for DECEMBER")
        self._get_stats(december_first)

