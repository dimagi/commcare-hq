from django.core.management.base import BaseCommand
from corehq.apps.reminders.models import (CaseReminderHandler,
    UI_COMPLEX, ON_DATETIME, REMINDER_TYPE_DEFAULT,
    RECIPIENT_SURVEY_SAMPLE)
from dimagi.utils.couch.database import iter_docs


class Command(BaseCommand):
    """
      The new reminders UI removes support for some edge cases, and the
    purpose of this script is to confirm that there are no reminder
    definitions which use those edge use cases.

    Usage:
        python manage.py check_for_old_reminders
    """
    args = ""
    help = ("A command which checks for edge use cases that are no longer"
        "supported in the new reminders UI")

    def get_reminder_definition_ids(self):
        result = CaseReminderHandler.view(
            "reminders/handlers_by_domain_case_type",
            include_docs=False,
        ).all()
        return [row["id"] for row in result]

    def check_for_ui_type(self, handler):
        if handler.ui_type != UI_COMPLEX:
            print "%s: Handler %s does not have advanced ui flag set" % (
                handler.domain, handler._id)

    def check_for_multiple_fire_time_types(self, handler):
        if len(handler.events) > 1:
            fire_time_type = handler.events[0].fire_time_type
            for event in handler.events[1:]:
                if event.fire_time_type != fire_time_type:
                    print ("%s: Handler %s references multiple fire time "
                        "types" % (handler.domain, handler._id))

    def check_for_datetime_criteria(self, handler):
        if handler.start_condition_type == ON_DATETIME:
            print ("%s: Handler %s starts on datetime criteria and is not a "
                "broadcast" % (handler.domain, handler._id))

    def check_for_case_group_recipient(self, handler):
        if handler.recipient == RECIPIENT_SURVEY_SAMPLE:
            print ("%s: Handler %s sends to case group and is not a "
                "broadcast" % (handler.domain, handler._id))

    def handle(self, *args, **options):
        ids = self.get_reminder_definition_ids()
        for handler_doc in iter_docs(CaseReminderHandler.get_db(), ids):
            handler = CaseReminderHandler.wrap(handler_doc)
            if handler.reminder_type == REMINDER_TYPE_DEFAULT:
                self.check_for_ui_type(handler)
                self.check_for_multiple_fire_time_types(handler)
                self.check_for_datetime_criteria(handler)
                self.check_for_case_group_recipient(handler)
