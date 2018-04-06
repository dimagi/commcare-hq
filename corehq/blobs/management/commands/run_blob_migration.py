from __future__ import absolute_import
from __future__ import unicode_literals
import logging
import os
import sys
from datetime import datetime

from django.core.management import BaseCommand, CommandError
from corehq.blobs.migrate import MIGRATIONS
from corehq.util.decorators import change_log_level
from corehq.util.teeout import tee_output


USAGE = """Usage: ./manage.py run_blob_migration [options] <slug>

Slugs:

{}

""".format('\n'.join(sorted(MIGRATIONS)))


class Command(BaseCommand):
    """
    Example: ./manage.py run_blob_migration [options] saved_exports
    """
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument(
            'slug',
            choices=sorted(MIGRATIONS),
            help="Migration slug: {}".format(', '.join(sorted(MIGRATIONS))),
        )
        parser.add_argument(
            '--log-dir',
            help="Migration log directory.",
        )
        parser.add_argument(
            '--reset',
            action="store_true",
            default=False,
            help="Discard any existing migration state.",
        )
        parser.add_argument(
            '--chunk-size',
            type=int,
            default=100,
            help="Maximum number of records to read from couch at once.",
        )

    @change_log_level('boto3', logging.WARNING)
    @change_log_level('botocore', logging.WARNING)
    def handle(self, slug=None, log_dir=None, reset=False, chunk_size=100,
               **options):
        try:
            migrator = MIGRATIONS[slug]
        except KeyError:
            raise CommandError(USAGE)

        def do_migration():
            total, skips = migrator.migrate(
                log_file,
                reset=reset,
                chunk_size=chunk_size,
            )
            if skips:
                sys.exit(skips)

        if log_dir is None:
            log_file = None
            do_migration()
        else:
            now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            summary_file = os.path.join(log_dir,
                "{}-blob-migration-{}-summary.txt".format(slug, now))
            log_file = os.path.join(log_dir,
                "{}-blob-migration-{}.txt".format(slug, now))
            assert not os.path.exists(summary_file), summary_file
            assert not os.path.exists(log_file), log_file
            with open(summary_file, "w", 1) as fh, tee_output(fh):
                do_migration()
