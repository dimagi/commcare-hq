from __future__ import absolute_import
from __future__ import unicode_literals
import dateutil.parser

from django.core.management import BaseCommand
from django.db import transaction

from corehq.apps.sms.models import SMS
from corehq.apps.smsbillables.models import SmsBillable
from corehq.util.log import with_progress_bar


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--start_datetime',
            type=dateutil.parser.parse,
        )
        parser.add_argument(
            '--end_datetime',
            type=dateutil.parser.parse,
        )

    def handle(self, **options):
        start_datetime = options.get('start_datetime')
        end_datetime = options.get('end_datetime')

        billables_to_reprocess = SmsBillable.objects.filter(
            gateway_fee__criteria__is_active=False,
            is_valid=True,
        )
        if start_datetime:
            billables_to_reprocess = billables_to_reprocess.filter(date_sent__gte=start_datetime)
        if end_datetime:
            billables_to_reprocess = billables_to_reprocess.filter(date_send__lt=end_datetime)

        for existing_billable in with_progress_bar(billables_to_reprocess):
            retrobill(existing_billable)


@transaction.atomic
def retrobill(existing_billable):
    existing_billable.is_valid = False
    existing_billable.save()
    sms_log = SMS.objects.get(couch_id=existing_billable.log_id)
    new_billable = SmsBillable.create(sms_log)
    new_billable.gateway_fee_conversion_rate = existing_billable.gateway_fee_conversion_rate
    new_billable.save()
