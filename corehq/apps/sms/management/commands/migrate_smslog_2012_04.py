import hashlib
from django.core.management.base import LabelCommand
from corehq.apps.sms.models import SMSLog

class Command(LabelCommand):
    help = "Migrates all existing MessageLog documents to the new SMSLog documents introduced in April 2012."
    args = ""
    label = ""

    def handle(self, *labels, **options):
        messages = SMSLog.view("sms/migrate_smslog_2012_04", include_docs=True)
        print "Migrating MessageLog to SMSLog"
        for message in messages:            
            try:
                message.doc_type = "SMSLog"
                message.base_doc = "MessageLog"
                message.couch_recipient_doc_type = "CouchUser"
                message.save()
            except Exception as e:
                print "There was an error migrating message %s." % (message._id)

