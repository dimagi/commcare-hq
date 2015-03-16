from django.core.management.base import BaseCommand
from corehq.apps.domain.models import Domain
from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.reminders.models import (CaseReminderHandler,
    REMINDER_TYPE_DEFAULT)


class Command(BaseCommand):
    args = ""
    help = ""

    def domain_has_active_reminders(self, domain):
        for handler in CaseReminderHandler.get_handlers(
            domain.name,
            reminder_type_filter=REMINDER_TYPE_DEFAULT
        ):
            if handler.active:
                return True
        return False

    def handle(self, *args, **options):
        for domain in Domain.get_all():
            if (
                self.domain_has_active_reminders(domain) and
                not domain_has_privilege(domain, privileges.REMINDERS_FRAMEWORK)
            ):
                print "%s has active reminders without a subscription" % domain.name
