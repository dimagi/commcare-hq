from django.core.management.base import BaseCommand, CommandError
from corehq.apps.smsforms.models import XFormsSession
from touchforms.formplayer.api import (
    get_raw_instance,
    InvalidSessionIdException,
)

class Command(BaseCommand):
    args = ""
    help = ""
    
    def handle(self, *args, **options):
        sessions = XFormsSession.view(
            "smsforms/open_sms_sessions_by_connection",
            include_docs=True
        ).all()
        for session in sessions:
            try:
                get_raw_instance(session.session_id)
            except InvalidSessionIdException:
                print "Closing %s %s" % (session.domain, session._id)
                session.end(False)
                session.save()
            except Exception as e:
                print "An unexpected error occurred when processing %s %s" % (session.domain, session._id)
                print e

