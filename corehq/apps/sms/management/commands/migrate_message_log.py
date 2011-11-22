import hashlib
from django.core.management.base import LabelCommand
from corehq.apps.sms.models import MessageLogOld, MessageLog

class Command(LabelCommand):
    help = "Migrates old django-based sms message log model of 2010 to new couch based model of Nov. 2011."
    args = ""
    label = ""

    def handle(self, *labels, **options):
        old_django_messages = MessageLogOld.objects.all()

        print "Migrating MessageLog"
        for message in old_django_messages:
            new_key = hashlib.md5("%s %s %s %s %s %s" % (
                message.couch_recipient,
                message.domain,
                message.phone_number,
                message.direction,
                message.date,
                message.text
            )).hexdigest()
            try:
                couch_message = MessageLog(_id=new_key,
                                            couch_recipiet=message.couch_recipient,
                                            domain=message.domain,
                                            phone_number=message.phone_number,
                                            direction=message.direction,
                                            date=message.date,
                                            text=message.text)
                couch_message.save()
            except Exception as e:
                print "There was an error migrating MessageLog with text %s to couch_recipient %s in domain %s" % (
                    message.text,
                    message.couch_recipient,
                    message.domain
                )
