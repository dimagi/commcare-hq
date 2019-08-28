
from django.core.management import BaseCommand

import dateutil.parser

from corehq.apps.domain.models import Domain
from corehq.apps.sms.models import SMS
from corehq.apps.smsbillables.models import SmsBillable


class Command(BaseCommand):
    help = 'Create SmsBillables for all SMSs in the given datetime range'

    def add_arguments(self, parser):
        parser.add_argument(
            'start_datetime',
            type=dateutil.parser.parse,
        )
        parser.add_argument(
            'end_datetime',
            type=dateutil.parser.parse,
        )
        parser.add_argument(
            '--create',
            action='store_true',
            default=False,
            help='Save SmsBillables in the database',
        )

    def handle(self, start_datetime, end_datetime, **options):
        num_sms = 0

        for domain in Domain.get_all():
            result = SMS.by_domain(
                domain.name,
                start_date=start_datetime,
                end_date=end_datetime,
            )

            for sms_log in result:
                if options.get('create', False):
                    SmsBillable.create(sms_log)
                    print('Created billable for SMS %s in domain %s from %s' \
                          % (sms_log.couch_id, domain.name, sms_log.date))
                else:
                    print('Found SMS %s in domain %s from %s' \
                          % (sms_log.couch_id, domain.name, sms_log.date))
                num_sms += 1

        print('Number of SMSs in datetime range: %d' % num_sms)
