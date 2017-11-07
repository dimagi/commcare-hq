from __future__ import absolute_import
from corehq.apps.sms.models import SMS
from corehq.messaging.smsbackends.icds_nic.models import SQLICDSBackend
from datetime import datetime
from django.core.management.base import BaseCommand

SUBSTRINGS = {
    'hin': {
        'aww_1': u'\u0906\u0901\u0917\u0928\u0935\u093e\u095c\u0940 \u0915\u0947\u0902\u0926\u094d\u0930 \u0926\u094d\u0935\u093e\u0930\u093e \u090f\u0915',
        'aww_2': u'\u091f\u0940.\u090f\u091a . \u0930. \u0935\u093f\u0924\u0930\u0923 :',
        'ls_1': u'\u091f\u0940.\u090f\u091a.\u0930.\u0935\u093f\u0924\u0930\u0923 :',
        'ls_2': u'\u0928\u093f\u092e\u094d\u0932\u093f\u0916\u093f\u0924 \u0906\u0901\u0917\u0928\u0935\u093e\u095c\u0940 ',
        'ls_6': u'\u0906\u0901\u0917\u0928\u0935\u093e\u095c\u0940 \u0915\u0947\u0902\u0926\u094d\u0930\u094b\u0902 \u0926\u094d\u0935\u093e\u0930\u093e',
    },
    'tel': {
        'aww_1': u'\u0c05\u0c02\u0c17\u0c28\u0c4d \u0c35\u0c3e\u0c21\u0c40 \u0c15\u0c47\u0c02\u0c26\u0c4d\u0c30\u0c02 ICDS',
        'aww_2': u'\u0c17\u0c43\u0c39 \u0c38\u0c02\u0c26\u0c30\u0c4d\u0c36\u0c28\u0c32\u0c41:',
        'ls_1': u'\u0c17\u0c43\u0c39 \u0c38\u0c02\u0c26\u0c30\u0c4d\u0c36\u0c28\u0c32\u0c41  ',
        'ls_2': u'\u0c17\u0c24 \u0c28\u0c46\u0c32 \u0c30\u0c4b\u0c1c\u0c41\u0c32\u0c4d\u0c32\u0c4b',
        'ls_6': u'\u0c35\u0c3e\u0c30\u0c3f\u0c15\u0c3f \u0c24\u0c17\u0c3f\u0c28 \u0c38\u0c39\u0c3e\u0c2f\u0c02',
    },
}


class Command(BaseCommand):
    help = ""

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def get_indicator_slug(self, sms):
        last_match = None
        num_matches = 0

        for lang_code, data in SUBSTRINGS.items():
            for slug, substring in data.items():
                if substring in sms.text:
                    last_match = slug
                    num_matches += 1

        return last_match, num_matches

    def handle(self, domain, **options):
        for sms in SMS.objects.filter(
            domain=domain,
            backend_api=SQLICDSBackend.get_api_id(),
            direction='O',
            processed=True,
            date__lt=datetime(2017, 6, 26),
        ):
            if sms.custom_metadata:
                continue

            slug, num_matches = self.get_indicator_slug(sms)
            if num_matches == 1:
                sms.custom_metadata = {'icds_indicator': slug}
                sms.save()
