import logging
from corehq.apps.sms.util import create_billable_for_sms
from dimagi.utils.couch.database import iter_docs
from django.core.management.base import LabelCommand
from corehq.apps.sms.models import SMSLog


class Command(LabelCommand):
    help = "Retroactively bills all the SMS messages that were not billed August 1 to to October 15, 2013."
    args = ""
    label = ""

    def handle(self, *labels, **options):
        db = SMSLog.get_db()

        # active_domains = db.view(
        #     "sms/by_domain",
        #     reduce=True,
        #     group_level=1,
        # ).all()
        # active_domains = [d['key'][0] for d in active_domains]
        active_domains = ['pathfinder']
        startkey = lambda d: [d, "SMSLog", "2013-08-01"]
        endkey = lambda d: [d, "SMSLog", "2013-10-15"]

        for domain in active_domains:
            data = db.view(
                "sms/by_domain",
                reduce=False,
                startkey=startkey(domain),
                endkey=endkey(domain),
            ).all()
            sms_ids = [d['id'] for d in data]
            for doc in iter_docs(db, sms_ids):
                sms_log = SMSLog.wrap(doc)
                if not sms_log.billed and sms_log.backend_api in [
                    'MACH',
                    # 'TROPO',
                    # 'UNICEL',
                ]:
                    # we're going to assume the SMS messages were sent successfully
                    # at the time they were actually sent
                    successful_responses = {
                        'MACH': "MACH RESPONSE +OK 01 message queued (dest=%s)" % sms_log.phone_number,
                        'TROPO': "<success>true</success>",
                        'UNICEL': "success",
                    }
                    print "Retroactively billing SMLog %s in domain %s" % (sms_log._id, sms_log.domain)
                    try:
                        create_billable_for_sms(
                            sms_log,
                            sms_log.backend_api,
                            delay=False,
                            response=successful_responses[sms_log.backend_api],
                        )
                    except Exception as e:
                        print "Retroactive bill was not successful due to error: %s" % e
                        logging.exception(e)
