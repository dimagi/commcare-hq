import datetime

from django.core.management.base import BaseCommand

from corehq.apps.sms.models import SMS
from corehq.apps.smsbillables.models import SmsBillable


class Command(BaseCommand):
    help = ""

    def _fix_sms(self, date_start, date_stop=None):
        query = SMS.objects.filter(
            date__gte=date_start,
            backend_api='TWILIO',
            domain__isnull=False
        ).exclude(domain__in=['ccqa'])
        if date_stop:
            query = query.filter(date__lt=date_stop)
        print(f"Found {query.count()} messages")
        available_ids = set(query.values_list('couch_id', flat=True))
        billed_query = SmsBillable.objects.filter(log_id__in=available_ids)
        total_billed = billed_query.count()
        total_bad = len(available_ids) - total_billed
        billed_ids = set(billed_query.values_list('log_id', flat=True))
        bad_sms = available_ids.difference(billed_ids)
        for sms_id in bad_sms:
            sms = SMS.objects.get(couch_id=sms_id)
            sms.processed = False
            sms.save()
            sms.requeue()
            print(sms_id)
        print("-------")
        print(f"Total fixed sms: {len(bad_sms)}")

    def handle(self, **options):
        october_first = datetime.datetime(2020, 10, 1)
        november_first = datetime.datetime(2020, 11, 1)
        december_first = datetime.datetime(2020, 12, 1)

        print("\n\nData for OCTOBER")
        self._fix_sms(october_first, november_first)

        # print("\n\nData for NOVEMBER")
        # self._get_stats(november_first, december_first)
        #
        # print("\n\nData for DECEMBER")
        # self._get_stats(december_first)
