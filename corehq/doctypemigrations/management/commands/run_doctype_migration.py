from optparse import make_option
from django.core.management import BaseCommand, CommandError
from corehq.doctypemigrations.migrator_instances import get_migrator_by_slug, \
    get_migrator_slugs

USAGE = """You may run either of the following commands

./manage.py run_doctype_migration <slug> --initial
./manage.py run_doctype_migration <slug> --continuous

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


class Command(BaseCommand):
    """
    Example: ./manage.py run_doctype_migration user_db_migration

    """
    help = USAGE
    option_list = BaseCommand.option_list + (
        make_option(
            '--initial',
            action='store_true',
            default=False,
        ),
        make_option(
            '--continuous',
            action='store_true',
            default=False,
        ),
    )

    def handle(self, migrator_slug=None, initial=None, continuous=None, **options):
        try:
            migrator = get_migrator_by_slug(migrator_slug)
        except KeyError:
            return
        if not initial and not continuous:
            raise CommandError('initial or continuous must be set')

        if initial:
            if migrator.last_seq:
                raise CommandError(MAYBE_YOU_WANT_TO_RUN_CONTINUOUS.format(migrator_slug))
            self.handle_initial(migrator)
        if continuous:
            if not migrator.last_seq:
                raise CommandError(MAYBE_YOU_WANT_TO_RUN_INITIAL.format(migrator_slug))
            self.handle_continuous(migrator)

    @staticmethod
    def handle_initial(migrator):
        migrator.phase_1_bulk_migrate()

    def handle_continuous(self, migrator):
        self.stderr.write("Starting continuous replication...")
        migration = migrator.phase_2_continuous_migrate_interactive()
        for status_update in migration:
            self.stdout.write('Read {} changes, saved seq {}\n'.format(
                status_update.changes_read, status_update.last_seq))
            if status_update.caught_up:
                self.stdout.write('All caught up!\n')
