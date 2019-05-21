from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import logging
import os
import sys
from datetime import datetime, timedelta

from django.core.management import BaseCommand, CommandError
from corehq.blobs.migrate import MIGRATIONS
from corehq.blobs.util import set_max_connections
from corehq.util.decorators import change_log_level
from corehq.util.teeout import tee_output
from six.moves import range


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
        add_argument(
            '--date-range',
            help=(
                "Creation date range of blobs to be migrated specified as one "
                "or two dates in YYYYMMDD format. If only one date is "
                "specified, it will be used as the end date, leaving the "
                "start date unbounded. Some migrations may not support this"
                "parameter. Example value: 20180109-20190109"
            ),
        )
        add_argument(
            '--process_day_by_day',
            action='store_true',
            default=False,
            help=(
                "Run migration for each day in the given date-range separately "
                "to allow cancelling and resuming on any day. Only applicable with date-range option"
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

        if "date_range" in options:
            rng = options["date_range"]
            if rng is None:
                options.pop("date_range")
            else:
                if "-" not in rng:
                    rng = (None, get_date(rng))
                else:
                    rng = rng.split("-")
                    if len(rng) != 2:
                        raise CommandError("bad date range: {}".format(rng))
                    rng = tuple(get_date(v) for v in rng)
                # date_range is a tuple containing two date values
                # a value of None means that side of the range is unbounded
                options["date_range"] = rng

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

        def _migrate():
            with tee_output(summary_file):
                try:
                    total, skips = migrator.migrate(log_file, **options)
                    if skips:
                        sys.exit(skips)
                except KeyboardInterrupt:
                    print("stopped by operator")
                    if options.get('date_range'):
                        print("while processing date range {}".format(options['date_range']))
                    sys.exit(1)

        process_day_by_day = options.pop('process_day_by_day')
        if 'date_range' in options and process_day_by_day:
            start, end = options.pop('date_range')
            num_days = (end - start).days
            for day in range(num_days + 1):
                date = start + timedelta(days=day)
                options['date_range'] = (date, date)
                print("Migrating for date {} ".format(date))
                _migrate()
                print("Finished migration for date {} ".format(date))
        else:
            _migrate()



def get_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        raise CommandError("bad date value: {}".format(value))
