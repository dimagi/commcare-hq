from corehq.apps.sms.models import SMSLog, CouchLog, ExpectedCallbackEventLog, LastReadMessage
from dimagi.utils.couch.database import iter_bulk_delete
from django.core.management.base import CommandError


class Command(BaseCommand):
    args = ""
    help = "Deletes messaging log docs no longer in use"

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

    def handle(self, *args, **options):
        print "Deleting SMSLog"
        iter_bulk_delete(SMSLog.get_db(), self.get_sms_couch_ids())

        print "Deleting CallLog"
        iter_bulk_delete(CallLog.get_db(), self.get_call_couch_ids())

        print "Deleting ExpectedCallbackEventLog"
        iter_bulk_delete(ExpectedCallbackEventLog.get_db(), self.get_callback_couch_ids())

        print "Deleting LastReadMessage"
        iter_bulk_delete(LastReadMessage.get_db(), self.get_lastreadmessage_couch_ids())
