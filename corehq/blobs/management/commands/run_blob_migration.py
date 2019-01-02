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
DEFAULT_BOTOCORE_MAX_POOL_CONNECTIONS = 10
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
        def add_argument(*args, **kw):
            name = args[-1].lstrip("-").replace("-", "_")
            self.option_names.add(name)
            parser.add_argument(*args, **kw)

        self.option_names = set()
        add_argument(
            'slug',
            choices=sorted(MIGRATIONS),
            help="Migration slug: {}".format(', '.join(sorted(MIGRATIONS))),
        )
        add_argument(
            '--log-dir',
            help="Migration log directory.",
        )
        add_argument(
            '--reset',
            action="store_true",
            default=False,
            help="Discard any existing migration state.",
        )
        add_argument(
            '--chunk-size',
            type=int,
            default=100,
            help="Maximum number of records to read from couch at once.",
        )
        add_argument(
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
        # drop options not added by this command
        for name in list(options):
            if name not in self.option_names:
                options.pop(name)
        if not migrator.has_worker_pool:
            num_workers = options.pop("num_workers")
            if num_workers != DEFAULT_WORKER_POOL_SIZE:
                print("--num-workers={} ignored because this migration "
                      "does not use a worker pool".format(num_workers))
        elif options["num_workers"] > DEFAULT_BOTOCORE_MAX_POOL_CONNECTIONS:
            set_max_connections(options["num_workers"])

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


def set_max_connections(num_workers):
    # see botocore.config.Config max_pool_connections
    # https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html
    from django.conf import settings
    from corehq.blobs import _db

    def update_config(name):
        config = getattr(settings, name)["config"]
        config["max_pool_connections"] = num_workers

    assert not _db, "get_blob_db() has been called"
    for name in ["S3_BLOB_DB_SETTINGS", "OLD_S3_BLOB_DB_SETTINGS"]:
        if getattr(settings, name, False):
            update_config(name)
