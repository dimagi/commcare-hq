from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.smsforms.models import SQLXFormsSession
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            dest="check",
            help="Include this option to check the counts but not do any updating",
        )

    def handle(self, **options):
        now = datetime.utcnow()
        stale_timestamp = now - timedelta(minutes=SQLXFormsSession.MAX_SESSION_LENGTH)

        stale_sessions = SQLXFormsSession.objects.filter(
            end_time__isnull=True,
            start_time__lte=stale_timestamp
        )

        historical_session_is_open_backfill = SQLXFormsSession.objects.filter(
            end_time__isnull=False,
            session_is_open=True
        )

        if options['check']:
            print("Stale sessions that need to be closed: %s" % stale_sessions.count())
            print("Historical session_is_open backfill: %s" % historical_session_is_open_backfill.count())
        else:
            stale_sessions.update(end_time=now, session_is_open=False)
            historical_session_is_open_backfill.update(session_is_open=False)
            print("Updates Complete")
