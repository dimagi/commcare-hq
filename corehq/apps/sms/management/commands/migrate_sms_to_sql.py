from corehq.apps.sms.models import SMSLog, SMS
from custom.fri.models import FRISMSLog
from dimagi.utils.couch.database import iter_docs
from django.core.management.base import BaseCommand
from optparse import make_option


class Command(BaseCommand):
    args = ""
    help = ("Migrates SMSLog to SMS")
    option_list = BaseCommand.option_list + (
        make_option("--balance_only",
                    action="store_true",
                    dest="balance_only",
                    default=False,
                    help="Include this option to only run the balancing step."),
    )

    def get_sms_couch_ids(self):
        result = SMSLog.view(
            'sms/by_domain',
            include_docs=False,
            reduce=False,
        ).all()
        return [row['id'] for row in result if row['key'][1] == 'SMSLog']

    def run_migration(self):
        count = 0
        ids = self.get_sms_couch_ids()
        total_count = len(ids)
        for doc in iter_docs(FRISMSLog.get_db(), ids):
            couch_sms = FRISMSLog.wrap(doc)
            try:
                couch_sms._migration_do_sync()
            except Exception as e:
                print 'Could not sync SMSLog %s: %s' % (couch_sms._id, e)

            count += 1
            if (count % 10000) == 0:
                print 'Processed %s / %s documents' % (count, total_count)

    def balance(self):
        sql_count = SMS.objects.count()
        couch_count = len(self.get_sms_couch_ids())
        print "SQL Count: %s, Couch Count: %s" % (sql_count, couch_count)

    def handle(self, *args, **options):
        if not options['balance_only']:
            self.run_migration()
        self.balance()
