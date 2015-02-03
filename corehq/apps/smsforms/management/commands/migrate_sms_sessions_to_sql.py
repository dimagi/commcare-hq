from django.core.management.base import BaseCommand
from corehq.apps.smsforms.models import XFormsSession, sync_sql_session_from_couch_session, SQLXFormsSession
from dimagi.utils.couch.database import iter_docs


class Command(BaseCommand):
    args = ""
    help = ""

    def handle(self, *args, **options):
        db = XFormsSession.get_db()
        session_ids = [row['id'] for row in db.view("smsforms/sessions_by_touchforms_id")]
        for session_doc in iter_docs(db, session_ids):
            couch_session = XFormsSession.wrap(session_doc)
            sync_sql_session_from_couch_session(couch_session)

        print 'migrated {} couch sessions. there are now {} in sql'.format(
            len(session_ids), SQLXFormsSession.objects.count()
        )
