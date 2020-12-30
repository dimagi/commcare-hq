import datetime

from django.core.management.base import BaseCommand

from corehq.apps.sms.models import SMS
from corehq.apps.smsbillables.models import SmsBillable


ALREADY_PROCESSED = [
    '2623d480fb6543f6ad42c935a284f94e',
    'b243eea914b646fb8d2229028ab9e8eb',
    '65d1b395d9da4eeab3cc1652bcece7bf',
    '7c7a0a91dbc34196bf230db549344de9',
    'e4ff612ea29f42478a5c0596cb5063fa',
    '818552cb9cb04a51954e2318666b89e6',
    '8b9414b3e2dd43128e5de576ad448447',
    'd26150fc36614b0885fb1c56b9c4c18f',
    '41b284f6706f4a82bac63c631a82d112',
    '988207093fac4b6b8b6f9d291dbf1aa6',
    'f8ca64f0fcfb49ce967bef7710c0f74c',
    'cec876ecc77544d18a8a69e442c7226d',
    'ca6eb16687d9472283da9c460e702a19',
    'bdcec77c191f4bf181c4b107949af7cc',
    '60b70505f3384949a8ccd2c36cffeb3e',
    '2b95f370075c41a38acd0896e3e9f679',
    'c23dc43571e5415d9442c37c24d67a53',
    '38af3175b6ea4809b856329bf340bdf4',
    '7224325a585b4fae8145252753acc4f9',
    '236d17bb091743c883e28284c6c1dbd3',
    '2bb9fa443b67487b97108b0e258fde37',
    '056c7961149d4af09b9a4a8a19c9c999',
    '0885b88f115d4d929c01530fc7e57205',
    '866e274d56a9496fa3ef07e1919da93a',
    '1a59e03b59094f94a3ba771cb5bab59c',
    'f3b9c5d93a934dcea152f22ac096e5d4',
    '27eee6cbcc6e470c89385bf423d8848c',
]


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
        bad_sms = bad_sms.difference(ALREADY_PROCESSED)
        skipped = []
        for sms_id in bad_sms:
            sms = SMS.objects.get(couch_id=sms_id)
            sms.processed = False
            sms.save()
            try:
                sms.requeue()
            except Exception:
                skipped.append(sms_id)
            print(sms_id)
        print("-------")
        total_fixed = len(bad_sms) - len(skipped)
        print(f"Total fixed sms: {total_fixed}")
        print(f"Total skipped: {len(skipped)}")
        print(skipped)

    def handle(self, **options):
        october_first = datetime.datetime(2020, 10, 1)
        november_first = datetime.datetime(2020, 11, 1)
        december_first = datetime.datetime(2020, 12, 1)

        # print("\n\nData for OCTOBER")
        # self._fix_sms(october_first, november_first)

        # print("\n\nData for NOVEMBER")
        # self._get_stats(november_first, december_first)
        #
        print("\n\nData for DECEMBER")
        self._fix_sms(december_first)
