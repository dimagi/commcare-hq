import sys
from optparse import make_option
from django.core.management import BaseCommand, CommandError
from corehq.blobs.migrate import MIGRATIONS


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
    )

    def handle(self, slug=None, file=None, **options):
        try:
            migrator = MIGRATIONS[slug]
        except KeyError:
            raise CommandError(USAGE)
        total, skips = migrator.migrate(file)
        if skips:
            sys.exit(skips)
