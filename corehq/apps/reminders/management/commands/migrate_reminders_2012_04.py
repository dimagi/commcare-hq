import hashlib
from django.core.management.base import LabelCommand
from corehq.apps.reminders.models import CaseReminderHandler, MATCH_REGEX

class Command(LabelCommand):
    help = "Migrates all existing CaseReminderHandler documents to the new model introduced in April 2012."
    args = ""
    label = ""

    def handle(self, *labels, **options):
        handlers = CaseReminderHandler.view("reminders/handlers_by_domain_case_type", include_docs=True)
        print "Migrating CaseReminderHandlers"
        for h in handlers:            
            try:
                h.start_property    = h.start
                h.start_value       = "^(ok|OK|\d\d\d\d-\d\d-\d\d)"
                h.start_date        = h.start
                h.start_match_type  = MATCH_REGEX
                h.save()
            except Exception as e:
                print "There was an error migrating handler %s." % (h._id)

