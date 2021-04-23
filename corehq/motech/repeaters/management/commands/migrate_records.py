from inspect import cleandoc

from django.core.management.base import BaseCommand

from corehq.util.log import with_progress_bar

from ...dbaccessors import (
    get_domains_that_have_repeat_records,
    get_repeaters_by_domain,
    iter_repeat_records_by_repeater,
)
from ...models import Repeater, RepeaterStub
from ...tasks import migrate_repeat_record


class Command(BaseCommand):
    help = cleandoc("""
    Migrate Couch RepeatRecords to SQL.

    If a Couch RepeatRecord cannot be migrated (usually because it
    encounters a ResourceConflict error when trying to set its
    "migrated" state) then this command can be run again, and
    already-migrated RepeatRecords will be skipped.

    See the "roll_back_record_migration" management command for
    instructions to roll the migration back, if necessary.
    """)

    def handle(self, *args, **options):
        # Migrate by domain to minimise impact on Repeat Record report
        domains = get_domains_that_have_repeat_records()
        for domain in with_progress_bar(domains):
            for repeater in get_repeaters_by_domain(domain):
                migrate_repeater(repeater)


def migrate_repeater(repeater: Repeater):
    for couch_record in iter_repeat_records_by_repeater(repeater.domain,
                                                        repeater.get_id):
        if couch_record.migrated:
            continue
        migrate_repeat_record.delay(repeater.repeater_stub, couch_record)
