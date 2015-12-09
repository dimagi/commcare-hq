import datetime
from corehq.apps.domain.models import Domain
from corehq.apps.sms.models import SMSLog
from corehq.apps.smsbillables.models import SmsBillable
from django.core.management import BaseCommand
from optparse import make_option


def str_to_int_tuple(string_tuple):
    return tuple([int(_) for _ in string_tuple])


class Command(BaseCommand):
    help = 'Create SmsBillables for all SMSs in the given datetime range'

    option_list = BaseCommand.option_list + (
        make_option('--create', action='store_true', default=False, help='Save SmsBillables in the database'),
    )

    def handle(self, *args, **options):
        num_sms = 0

        start_datetime = datetime.datetime(*str_to_int_tuple(args[0:6]))
        end_datetime = datetime.datetime(*str_to_int_tuple(args[6:12]))

        for domain in Domain.get_all():
            key = [domain.name, 'SMSLog']
            sms_docs = SMSLog.get_db().view('sms/by_domain',
                                            reduce=False,
                                            startkey=key + [start_datetime.isoformat()],
                                            endkey=key + [end_datetime.isoformat(), {}],
            )

            for sms_doc in sms_docs:
                sms_log = SMSLog.get(sms_doc['id'])
                if options.get('create', False):
                    SmsBillable.create(sms_log)
                    print 'Created billable for SMSLog %s in domain %s from %s' \
                          % (sms_doc['id'], domain.name, sms_log.date)
                else:
                    print 'Found SMSLog %s in domain %s from %s' \
                          % (sms_doc['id'], domain.name, sms_log.date)
                num_sms += 1

        print 'Number of SMSs in datetime range: %d' % num_sms
