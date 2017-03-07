from __future__ import print_function
from django.core.management.base import BaseCommand, CommandError
from corehq.apps.sms.models import SMS
from corehq.apps.users.models import CouchUser


class Command(BaseCommand):
    args = "<domain1 domain2 ... >"
    help = "Fix couch_recipient_doc_type on SMS entries."

    def handle(self, *args, **options):
        if len(args) == 0:
            raise CommandError("Usage: python manage.py fix_smslog_recipient_doc_type <domain1 domain2 ...>")

        for domain in args:
            print("*** Processing Domain %s ***" % domain)
            user_cache = {}
            for msg in SMS.by_domain(domain):
                if msg.couch_recipient:
                    if msg.couch_recipient_doc_type != "CommCareCase":
                        user = None
                        if msg.couch_recipient in user_cache:
                            user = user_cache[msg.couch_recipient]
                        else:
                            try:
                                user = CouchUser.get_by_user_id(msg.couch_recipient)
                            except Exception:
                                user = None
                            if user is None:
                                print("Could not find user %s" % msg.couch_recipient)
                        user_cache[msg.couch_recipient] = user
                        if user and msg.couch_recipient_doc_type != user.doc_type:
                            msg.couch_recipient_doc_type = user.doc_type
                            msg.save()
                else:
                    if msg.couch_recipient_doc_type is not None or msg.couch_recipient is not None:
                        msg.couch_recipient = None
                        msg.couch_recipient_doc_type = None
                        msg.save()
