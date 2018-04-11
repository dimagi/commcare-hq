from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.smsforms.models import SQLXFormsSession
from datetime import datetime
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
        open_sessions = SQLXFormsSession.objects.filter(
            current_action_due__isnull=True,
            end_time__isnull=True
        )

        closed_sessions = SQLXFormsSession.objects.filter(
            current_action_due__isnull=True,
            end_time__isnull=False
        )

        if options['check']:
            print("Open sessions to update: %s" % open_sessions.count())
            print("Closed sessions to update: %s" % closed_sessions.count())
        else:
            kwargs = {
                'session_is_open': True,
                'phone_number': '',
                'expire_after': SQLXFormsSession.MAX_SESSION_LENGTH,
                'reminder_intervals': [],
                'current_reminder_num': 0,
                'current_action_due': datetime(9999, 12, 31),
                'submit_partially_completed_forms': False,
                'include_case_updates_in_partial_submissions': False,
            }
            open_sessions.update(**kwargs)
            print("Open sessions update complete")

            kwargs['session_is_open'] = False
            closed_sessions.update(**kwargs)
            print("Closed sessions update complete")
