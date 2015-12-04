"""
ATTENTION!
If you see this file after the year 2015, please delete it immediately.
"""
import sys
from django.core.management.base import BaseCommand
from datetime import datetime
from corehq.apps.sofabed.models import FormData
from corehq.pillows.xform import XFormPillow
from corehq.pillows.reportxform import ReportXFormPillow
from pillowtop.feed.interface import Change


class Command(BaseCommand):
    help = ("Send all form submitted between Oct 28 7:30am UTC and 8:10am UTC"
            "to elasticsearch.  I checked, there are 4697 of 'em")

    def handle(self, *args, **options):
        start = datetime(2015, 10, 28, 7, 0)
        end = datetime(2015, 10, 28, 9, 0)
        # I didn't see any couch views which can get forms in a date range
        # without a domain, so I'm using FormData.
        form_ids = (FormData.objects.filter(received_on__range=(start, end))
                    .values_list('instance_id', flat=True))

        msg = "Really resave {} forms? (y/n)\n".format(len(form_ids))
        if raw_input(msg) != "y":
            print "cancelling"
            sys.exit()

        for form_id in form_ids:
            XFormPillow().processor(Change(id=form_id, sequence_id=None), None)
            ReportXFormPillow().processor(Change(id=form_id, sequence_id=None), None)
