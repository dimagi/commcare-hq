from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import logging
import os
import sys
from datetime import datetime

from django.core.management import BaseCommand, CommandError
from corehq.blobs.migrate import MIGRATIONS
from corehq.util.decorators import change_log_level
from corehq.util.teeout import tee_output


DEFAULT_WORKER_POOL_SIZE = 10
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
            dest="chunk_size",  # redundant arg for grep
            type=int,
            default=100,
            help="Maximum number of records to read from couch at once.",
        )
        parser.add_argument(
            '--num-workers',
            type=int,
            default=DEFAULT_WORKER_POOL_SIZE,
            help=(
                "Worker pool size for parallel processing. This option is "
                "ignored by migration types that do not support it."
            ),
        )

    @change_log_level('boto3', logging.WARNING)
    @change_log_level('botocore', logging.WARNING)
    def handle(self, slug, log_dir=None, **options):
        try:
            migrator = MIGRATIONS[slug]
        except KeyError:
            raise CommandError(USAGE)
        if not migrator.has_worker_pool:
            num_workers = options.pop("num_workers")
            if num_workers != DEFAULT_WORKER_POOL_SIZE:
                print("--num-workers={} ignored because this migration "
                      "does not use a worker pool".format(num_workers))

        if log_dir is None:
            summary_file = log_file = None
        else:
            now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            summary_file = os.path.join(log_dir,
                "{}-blob-migration-{}-summary.txt".format(slug, now))
            log_file = os.path.join(log_dir,
                "{}-blob-migration-{}.txt".format(slug, now))
            assert not os.path.exists(summary_file), summary_file
            assert not os.path.exists(log_file), log_file

        with tee_output(summary_file):
            try:
                total, skips = migrator.migrate(log_file, **options)
                if skips:
                    sys.exit(skips)
            except KeyboardInterrupt:
                print("stopped by operator")
                sys.exit(1)
