import logging
import sys
from optparse import make_option
from django.core.management import BaseCommand, CommandError
from corehq.blobs.migrate import MIGRATIONS
from corehq.util.decorators import change_log_level


USAGE = """Usage: ./manage.py run_blob_migration [options] <slug>

Slugs:

{}

""".format('\n'.join(sorted(MIGRATIONS)))


class Command(BaseCommand):
    """
    Example: ./manage.py run_blob_migration [options] saved_exports
    """
    help = USAGE
    option_list = BaseCommand.option_list + (
        make_option('--file', help="Migration intermediate storage file."),
        make_option('--reset', action="store_true", default=False,
            help="Discard any existing migration state."),
    )

    @change_log_level('boto3', logging.WARNING)
    @change_log_level('botocore', logging.WARNING)
    def handle(self, slug=None, file=None, reset=False, **options):
        try:
            migrator = MIGRATIONS[slug]
        except KeyError:
            raise CommandError(USAGE)
        total, skips = migrator.migrate(file, reset=reset)
        if skips:
            sys.exit(skips)
