import logging
from django.core.management.base import BaseCommand
from corehq.apps.smsforms.models import XFormsSession, sync_sql_session_from_couch_session, SQLXFormsSession
from dimagi.utils.couch.database import iter_docs


class Command(BaseCommand):
    args = ""
    help = ""

    def handle(self, *args, **options):
        db = XFormsSession.get_db()
        session_ids = [row['id'] for row in db.view("smsforms/sessions_by_touchforms_id")]
        errors = []
        for session_doc in iter_docs(db, session_ids):
            try:
                couch_session = XFormsSession.wrap(session_doc)
                sync_sql_session_from_couch_session(couch_session)
            except Exception as e:
                logging.exception('problem migrating session {}: {}'.format(session_doc['_id'], e))
                errors.append(session_doc['_id'])

        print 'migrated {} couch sessions. there are now {} in sql'.format(
            len(session_ids) - len(errors), SQLXFormsSession.objects.count()
        )
        if errors:
            print 'errors: {}'.format(', '.join(errors))
