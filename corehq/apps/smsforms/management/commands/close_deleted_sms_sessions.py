from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from corehq.apps.smsforms.models import SQLXFormsSession, XFORMS_SESSION_SMS
from touchforms.formplayer.api import (
    get_raw_instance,
    InvalidSessionIdException,
)


class Command(BaseCommand):
    args = ""
    help = ""
    
    def handle(self, *args, **options):
        sessions = SQLXFormsSession.objects.filter(
            Q(session_type__isnull=True) | Q(session_type=XFORMS_SESSION_SMS),
            end_time__isnull=True,
        ).all()
        for session in sessions:
            try:
                get_raw_instance(session.session_id)['output']
            except InvalidSessionIdException:
                print "Closing %s %s" % (session.domain, session._id)
                session.end(False)
                session.save()
            except Exception as e:
                print "An unexpected error occurred when processing %s %s" % (session.domain, session._id)
                print e
