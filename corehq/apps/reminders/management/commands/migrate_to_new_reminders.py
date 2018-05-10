from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from corehq.apps.domain.models import Domain
from corehq.toggles import REMINDERS_MIGRATION_IN_PROGRESS
from corehq.apps.reminders.models import (
    CaseReminderHandler,
    REMINDER_TYPE_DEFAULT,
    REMINDER_TYPE_KEYWORD_INITIATED,
    REMINDER_TYPE_SURVEY_MANAGEMENT,
    UI_SIMPLE_FIXED,
    EVENT_AS_OFFSET,
)
from django.core.management.base import BaseCommand
from six import moves


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            "--check",
            action="store_true",
            dest="check",
            default=False,
            help="Check if the migration can proceed but don't make changes",
        )

    def can_migrate(self, handler):
        return (
            handler.reminder_type == REMINDER_TYPE_DEFAULT and
            handler.ui_type == UI_SIMPLE_FIXED and
            handler.event_interpretation == EVENT_AS_OFFSET
        )

    def should_skip(self, handler):
        return handler.reminder_type in (REMINDER_TYPE_KEYWORD_INITIATED, REMINDER_TYPE_SURVEY_MANAGEMENT)

    def migration_already_done(self, domain_obj):
        if domain_obj.uses_new_reminders:
            print("'%s' already users new reminders, nothing to do" % domain_obj.name)
            return True

        return False

    def ensure_migration_flag_enabled(self, domain):
        while not REMINDERS_MIGRATION_IN_PROGRESS.enabled(domain):
            moves.input("Please enable REMINDERS_MIGRATION_IN_PROGRESS for '%s' and hit enter..." % domain)

        print("REMINDERS_MIGRATION_IN_PROGRESS enabled for %s" % domain)

    def get_handlers_to_migrate(self, domain):
        handlers = CaseReminderHandler.view(
            'reminders/handlers_by_domain_case_type',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True
        ).all()

        return [handler for handler in handlers if not self.should_skip(handler)]

    def can_perform_migration(self, handlers):
        cannot_be_migrated = []
        for handler in handlers:
            if not self.can_migrate(handler):
                cannot_be_migrated.append(handler)

        if cannot_be_migrated:
            print("The following configurations can't be migrated:")
            for handler in cannot_be_migrated:
                print("%s %s" % (handler._id, handler.reminder_type))

            return False

        return True

    def migrate_handlers(self, handlers):
        pass

    def handle(self, domain, **options):
        check_only = options['check']
        domain_obj = Domain.get_by_name(domain)

        if self.migration_already_done(domain_obj):
            return

        if not check_only:
            self.ensure_migration_flag_enabled(domain)

        handlers = self.get_handlers_to_migrate(domain)
        if not self.can_perform_migration(handlers):
            return

        print("Migration can proceed")

        if check_only:
            return

        self.migrate_handlers(handlers)
