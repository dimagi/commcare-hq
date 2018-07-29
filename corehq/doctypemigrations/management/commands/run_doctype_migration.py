from __future__ import absolute_import
from __future__ import unicode_literals
import re
from django.core.management import BaseCommand, CommandError
from corehq.doctypemigrations.migrator_instances import get_migrator_by_slug, \
    get_migrator_slugs
from six.moves import input

USAGE = """You may run either of the following commands

./manage.py run_doctype_migration <slug> --stats
./manage.py run_doctype_migration <slug> --initial
./manage.py run_doctype_migration <slug> --continuous
./manage.py run_doctype_migration <slug> --cleanup

with with the following slugs:

{}

""".format('\n'.join(get_migrator_slugs()))

MAYBE_YOU_WANT_TO_RUN_CONTINUOUS = """You have already run an initial migration.
Run

./manage.py run_doctype_migration {} --continuous

for continuous replication starting where you left off.
"""

MAYBE_YOU_WANT_TO_RUN_INITIAL = """You have not yet run an initial migration.
Run

./manage.py run_doctype_migration {} --initial

to do a bulk migrate before continuous replication.
"""

CANNOT_RUN_CONTINUOUS_AFTER_CLEANUP = """You have already run cleanup for this migration.
You cannot run --continuous after --cleanup.

This is actually very important: if you were to run --continuous again, that would
replicate changes from the source db to the target db
resulting in the docs deleted in cleanup also being deleted from the target db!

You're welcome.
"""


class Command(BaseCommand):
    """
    Example: ./manage.py run_doctype_migration user_db_migration

    """
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument(
            'migrator_slug',
        )
        parser.add_argument(
            '--initial',
            action='store_true',
            default=False,
            help="Do a full, initial bulk migration.",
        )
        parser.add_argument(
            '--continuous',
            action='store_true',
            default=False,
            help=("Start a continuous migration to keep things topped off "
                  "based on the changes feed.  This should be run in a screen "
                  "session and cancelled with ^C once it's no longer needed."),
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            default=False,
            help="Delete the old documents still in the source db.",
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            default=False,
            help="Output misc info about the status of the migration.",
        )
        parser.add_argument(
            '--erase-continuous-progress',
            action='store_true',
            default=False,
        )

    def handle(self, migrator_slug, initial=None, continuous=None, cleanup=None,
               stats=None, erase_continuous_progress=None, **options):
        try:
            migrator = get_migrator_by_slug(migrator_slug)
        except KeyError:
            raise CommandError(USAGE)
        if not any((initial, continuous, cleanup, stats, erase_continuous_progress)):
            raise CommandError('initial, continuous, cleanup, stats, or '
                               'erase_continuous_progress must be set')
        if cleanup and (initial or continuous):
            raise CommandError('cleanup must be run alone')

        if stats:
            self.handle_stats(migrator)
        if initial:
            if migrator.last_seq:
                raise CommandError(MAYBE_YOU_WANT_TO_RUN_CONTINUOUS.format(migrator_slug))
            self.handle_initial(migrator)
        if erase_continuous_progress:
            if not migrator.original_seq:
                CommandError(MAYBE_YOU_WANT_TO_RUN_INITIAL.format(migrator_slug))
            if migrator.cleanup_complete:
                raise CommandError(CANNOT_RUN_CONTINUOUS_AFTER_CLEANUP)
            self.handle_erase_continuous_progress(migrator)
        if continuous:
            if not migrator.last_seq:
                raise CommandError(MAYBE_YOU_WANT_TO_RUN_INITIAL.format(migrator_slug))
            if migrator.cleanup_complete:
                raise CommandError(CANNOT_RUN_CONTINUOUS_AFTER_CLEANUP)
            self.handle_continuous(migrator)
        if cleanup:
            confirmation = input(
                "Cleanup will remove doc_types ({}) from db {}\n"
                "I recommend running './manage.py delete_doc_conflicts' "
                "first or some docs might not actually be deleted.\n"
                "Are you sure you want to proceed? [y/n]"
                .format(', '.join(migrator.doc_types), migrator.source_db))
            if confirmation == 'y':
                if migrator.docs_are_replicating():
                    self.stdout.write(
                        "It looks like replication is still happening, please track "
                        "down and cancel before attempting to cleanup, lest you "
                        "replicate the deletions. Yikes!")
                    return
                self.handle_cleanup(migrator)

    @staticmethod
    def handle_initial(migrator):
        migrator.phase_1_bulk_migrate()

    def handle_continuous(self, migrator):
        self.stderr.write("Starting continuous replication...")
        migration = migrator.phase_2_continuous_migrate_interactive()
        for status_update in migration:
            self.stdout.write('Read {} changes, saved seq {}'.format(
                status_update.changes_read, status_update.last_seq))
            if status_update.caught_up:
                self.stdout.write('All caught up!')

    def handle_erase_continuous_progress(self, migrator):
        migrator.erase_continuous_progress()

    def handle_cleanup(self, migrator):
        migrator.phase_3_clean_up()

    def handle_stats(self, migrator):
        [(source_db, source_counts),
         (target_db, target_counts)] = migrator.get_doc_counts()
        self.stdout.write('Source DB: {}'.format(_scrub_uri(source_db.uri)))
        self.stdout.write('Target DB: {}'.format(_scrub_uri(target_db.uri)))
        self.stdout.write('')
        self.stdout.write('{:^30}\tSource\tTarget'.format('doc_type'))
        for doc_type in sorted(migrator.doc_types):
            self.stdout.write(
                '{:<30}\t{}\t{}'
                .format(doc_type, source_counts[doc_type], target_counts[doc_type]))


def _scrub_uri(uri):
    return re.sub(r'//(.*):(.*)@', r'//\1:******@', uri)
