from corehq.apps.ivr.models import Call
from corehq.apps.sms.models import (SMSLog, SMS, CallLog, LastReadMessage,
    ExpectedCallbackEventLog, ExpectedCallback, SQLLastReadMessage,
    MigrationStatus)
from custom.fri.models import FRISMSLog
from dimagi.utils.couch.database import iter_docs
from django.core.management.base import BaseCommand
from optparse import make_option


class Command(BaseCommand):
    args = ""
    help = ("Syncs all messaging logs stored in Couch to Postgres")
    option_list = BaseCommand.option_list + (
        make_option("--balance-only",
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

    def get_call_couch_ids(self):
        result = CallLog.view(
            'sms/by_domain',
            include_docs=False,
            reduce=False,
        ).all()
        return [row['id'] for row in result if row['key'][1] == 'CallLog']

    def get_callback_couch_ids(self):
        result = ExpectedCallbackEventLog.view(
            'sms/expected_callback_event',
            include_docs=False,
        ).all()
        return [row['id'] for row in result]

    def get_lastreadmessage_couch_ids(self):
        result = LastReadMessage.view(
            'sms/last_read_message',
            startkey=['by_anyone'],
            endkey=['by_anyone', {}],
            include_docs=False,
        ).all()
        return [row['id'] for row in result]

    def get_sms_and_call_couch_count(self):
        result = SMSLog.view(
            'sms/by_domain',
            include_docs=False,
            reduce=True,
        ).all()
        if result:
            return result[0]['value']
        return 0

    def get_sms_and_call_sql_count(self):
        return SMS.objects.count() + Call.objects.count()

    def clean_doc(self, doc):
        """
        Some old docs apparently have +00:00Z at the end of the date string,
        which is not a valid timezone specification.

        Also, because of http://manage.dimagi.com/default.asp?111189, there's
        9 docs with very long phone numbers that should just be replaced
        with null because there was no recipient to those sms.
        """
        date = doc.get('date')
        if isinstance(date, basestring) and date.endswith('+00:00Z'):
            date = date[:-7] + 'Z'
            doc['date'] = date

        phone_number = doc.get('phone_number')
        if isinstance(phone_number, basestring) and len(phone_number) > 126:
            doc['phone_number'] = None

    def migrate_model(self, get_couch_ids_method, couch_model, errors):
        count = 0
        ids = get_couch_ids_method()
        total_count = len(ids)
        for doc in iter_docs(couch_model.get_db(), ids):
            try:
                self.clean_doc(doc)
                couch_obj = couch_model.wrap(doc)
                couch_obj._migration_do_sync()
            except Exception as e:
                errors.append('Could not sync %s %s: %s' % (couch_model.__name__, doc['_id'], e))

            count += 1
            if (count % 10000) == 0:
                print 'Processed %s / %s %s documents' % (count, total_count, couch_model.__name__)

    def run_migration(self):
        errors = []
        self.migrate_model(self.get_sms_couch_ids, FRISMSLog, errors)
        self.migrate_model(self.get_call_couch_ids, CallLog, errors)
        self.migrate_model(self.get_callback_couch_ids, ExpectedCallbackEventLog, errors)
        self.migrate_model(self.get_lastreadmessage_couch_ids, LastReadMessage, errors)

        for error in errors:
            print error

        if len(errors) > 0:
            print "ERROR: %s error(s) occurred during migration. Please investigate before continuing." % len(errors)
        else:
            print "No errors occurred during migration."

    def balance_model(self, get_couch_ids_method, sql_model):
        sql_count = sql_model.objects.count()
        # Unfortunately, there's not a better way to do this. Two of the couch models
        # have views without a reduce, and the other two that have a view with a reduce
        # require querying on domain as part of the criteria.
        couch_count = len(get_couch_ids_method())

        print "%s / %s %ss migrated" % (sql_count, couch_count, sql_model.__name__)
        return couch_count == sql_count

    def sanity_check_sms_and_call_combined(self):
        """
        This is here just to make sure we didn't miss anything in the sms/by_domain view,
        which is shared between the SMSLog and CallLog models.
        """
        couch_count = self.get_sms_and_call_couch_count()
        sql_count = self.get_sms_and_call_sql_count()
        print "%s / %s SMSs and Calls migrated" % (sql_count, couch_count)
        return couch_count == sql_count

    def balance(self):
        sms_balances = self.balance_model(self.get_sms_couch_ids, SMS)
        call_balances = self.balance_model(self.get_call_couch_ids, Call)
        sms_and_call_balances = self.sanity_check_sms_and_call_combined()
        callback_balances = self.balance_model(self.get_callback_couch_ids, ExpectedCallback)
        lastreadmessage_balances = self.balance_model(self.get_lastreadmessage_couch_ids, SQLLastReadMessage)
        if not (
            sms_balances and
            call_balances and
            sms_and_call_balances and
            callback_balances and
            lastreadmessage_balances
        ):
            print "***ERROR: one or more of the above counts do not match. Please investigate before continuing."

    def handle(self, *args, **options):
        if not options['balance_only']:
            self.run_migration()
            MigrationStatus.set_migration_completed(MigrationStatus.MIGRATION_LOGS)
        self.balance()
