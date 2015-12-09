from corehq.apps.domain.models import Domain
from corehq.apps.sms.phonenumbers_helper import parse_phone_number, PhoneNumberParseException
from corehq.apps.smsbillables.models import SmsBillable
from django.core.management.base import LabelCommand
from corehq.apps.sms.models import SMSLog
import datetime


class Command(LabelCommand):
    help = "retrobill SMS with invalid phonenumbers during January 2014"
    args = ""
    label = ""

    def handle(self, *args, **options):
        billables_created = 0
        for domain in Domain.get_all():
            key = [domain.name, 'SMSLog']
            start_date = [datetime.datetime(2014, 1, 1).isoformat()]
            end_date = [datetime.datetime(2014, 1, 24).isoformat()]
            sms_docs = SMSLog.get_db().view('sms/by_domain',
                                            reduce=False,
                                            startkey=key + start_date,
                                            endkey=key + end_date + [{}])
            for sms_doc in sms_docs:
                sms_log = SMSLog.get(sms_doc['id'])
                try:
                    if sms_log.phone_number is not None:
                        parse_phone_number(sms_log.phone_number)
                except PhoneNumberParseException:
                    billables = SmsBillable.objects.filter(log_id=sms_log._id)
                    if len(billables) == 0:
                        SmsBillable.create(sms_log)
                        billables_created += 1
                        print 'created SmsBillable for invalid number %s in domain %s, id=%s'\
                              % (sms_log.phone_number, domain.name, sms_log._id)
                    elif len(billables) > 1:
                        print "Warning: >1 SmsBillable exists for SMSLog with id=%" % sms_log._id
        print 'Number of SmsBillables created: %d' % billables_created
        print 'Completed retrobilling.'
