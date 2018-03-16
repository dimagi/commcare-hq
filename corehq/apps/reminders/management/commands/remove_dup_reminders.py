from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management.base import BaseCommand
from corehq.apps.reminders.models import (CaseReminder, CaseReminderHandler,
    CASE_CRITERIA)
from corehq.messaging.signals import messaging_case_changed_receiver
from casexml.apps.case.models import CommCareCase


class Command(BaseCommand):
    """
    Usage:
        python manage.py remove_dup_reminders
            - displays all duplicate reminders
        python manage.py remove_dup_reminders --fix
            - displays and removes all duplicate reminders
    """

    help = ("A command which removes duplicate reminder instances created due "
        "to race conditions")

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            dest="fix",
            default=False,
            help="Include this option to automatically fix any "
                 "duplicates where possible.",
        )

    def reminder_to_json(self, r):
        j = r.to_json()
        del j["_id"]
        del j["_rev"]
        if "lock_date" in j:
            del j["lock_date"]
        return j

    def reminders_match(self, r1, r2):
        json1 = self.reminder_to_json(r1)
        json2 = self.reminder_to_json(r2)
        return json1 == json2

    def handle(self, **options):
        num_dups = 0
        make_fixes = options["fix"]
        ids = {}
        rows = CaseReminder.view("reminders/by_domain_handler_case",
            include_docs=False).all()

        for row in rows:
            row_key = row["key"]
            if row_key[2]:
                ids_key = "|".join(row_key)
                if ids_key in ids:
                    ids[ids_key].append(row["id"])
                else:
                    ids[ids_key] = [row["id"]]

        for k, v in ids.items():
            if len(v) > 1:
                num_dups += 1
                split_key = k.split("|")
                print("Duplicate found: ", split_key)

                handler = CaseReminderHandler.get(split_key[1])
                if handler.start_condition_type != CASE_CRITERIA:
                    print ("ERROR: Duplicate with the above key is not a case "
                        "criteria reminder")
                    continue

                all_match = True
                reminders = [CaseReminder.get(i) for i in v]
                for r in reminders[1:]:
                    all_match = all_match and self.reminders_match(reminders[0], r)
                if all_match:
                    if make_fixes:
                        print("Removing duplicate(s)...")
                        for r in reminders[1:]:
                            r.retire()
                        c = CommCareCase.get(split_key[2])
                        messaging_case_changed_receiver(None, c)
                else:
                    print("ERROR: Not all of the reminders with the above key match")

        print("%s Duplicate(s) were found" % num_dups)

