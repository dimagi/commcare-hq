from django.core.management.base import LabelCommand

from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import SmsUsageFee

class Command(LabelCommand):
    help = "bootstrap usage fees"
    args = ""
    label = ""

    def handle(self, *args, **options):
        SmsUsageFee.create_new(INCOMING, 0.01)
        SmsUsageFee.create_new(OUTGOING, 0.01)
        print "Updated usage fees."
