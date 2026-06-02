import gzip
import json
import logging
import os
import zipfile
from argparse import ArgumentTypeError
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.dump_reload.const import DATETIME_FORMAT
from corehq.apps.dump_reload.couch import CouchDataDumper
from corehq.apps.dump_reload.couch.dump import DomainDumper, ToggleDumper
from corehq.apps.dump_reload.sql import SqlDataDumper
from corehq.apps.dump_reload.sql.filters import DEFAULT_CHUNK_SIZE
from corehq.apps.dump_reload.timing import format_rate
from corehq.util.timer import TimingContext

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    # This doesn't include SyncLog data
    help = "Dump a domain's data to disk."

    def add_arguments(self, parser):
        parser.add_argument('domain_name')
        parser.add_argument(
            '-e', '--exclude', dest='exclude', action='append', default=[],
            help='An app_label, app_label.ModelName or CouchDB doc_type to exclude '
                 '(use multiple --exclude to exclude multiple apps/models).'
        )
        parser.add_argument(
            '-i', '--include', dest='include', action='append', default=[],
            help='An app_label, app_label.ModelName or CouchDB doc_type to include '
                 '(use multiple --include to include multiple apps/models).'
        )
        output_group = parser.add_mutually_exclusive_group()
        output_group.add_argument(
            '--console', action='store_true', default=False, dest='console',
            help='Write output to the console instead of to file.'
        )
        output_group.add_argument(
            '--dir', dest='dir',
            help='Optionally specify a directory to write the file to. '
                 'The directory will be created if it does not exist.',
        )
        parser.add_argument('--dumper', dest='dumpers', action='append', default=[],
                            help='Dumper slug to run (use multiple --dumper to run multiple dumpers).')
        parser.add_argument(
            '--sql-chunk-size', dest='sql_chunk_size', type=positive_int, default=DEFAULT_CHUNK_SIZE,
            help=f'Number of rows to fetch per query when dumping SQL data (default: {DEFAULT_CHUNK_SIZE}).'
        )

    def handle(self, domain_name, **options):
        excludes = options.get('exclude')
        includes = options.get('include')
        console = options.get('console')
        show_traceback = options.get('traceback')
        requested_dumpers = options.get('dumpers')
        output_dir = options.get('dir')
        sql_chunk_size = options.get('sql_chunk_size', DEFAULT_CHUNK_SIZE)

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        self.utcnow = datetime.utcnow().strftime(DATETIME_FORMAT)
        zipname = 'data-dump-{}-{}.zip'.format(domain_name, self.utcnow)
        if output_dir:
            zipname = os.path.join(output_dir, zipname)

        self.stdout.ending = None
        meta = {}  # {dumper_slug: {model_name: count}}
        timing_data = {}  # {dumper_slug: {'total': secs, 'models': {label: secs}}}
        # domain dumper should be first since it validates domain exists
        for dumper in [DomainDumper, SqlDataDumper, CouchDataDumper, ToggleDumper]:
            if requested_dumpers and dumper.slug not in requested_dumpers:
                continue

            filename = _get_dump_stream_filename(dumper.slug, domain_name, self.utcnow, path=output_dir)
            stream = self.stdout if console else gzip.open(filename, 'wt')
            if dumper is SqlDataDumper:
                dumper_instance = dumper(domain_name, excludes, includes, chunk_size=sql_chunk_size)
            else:
                dumper_instance = dumper(domain_name, excludes, includes)
            with TimingContext(dumper.slug) as dumper_timer:
                try:
                    meta[dumper.slug] = dumper_instance.dump(stream)
                except Exception as e:
                    if show_traceback:
                        raise
                    raise CommandError("Unable to serialize database: %s" % e)
                finally:
                    if stream and not console:
                        stream.close()

            logger.info(f"[timing] dumper '{dumper.slug}' finished in {dumper_timer.duration:.2f}s")
            timing_data[dumper.slug] = {
                'total': dumper_timer.duration,
                'models': dict(dumper_instance.timer.totals),
            }

            if not console:
                with zipfile.ZipFile(zipname, mode='a', allowZip64=True) as z:
                    z.write(filename, '{}.gz'.format(dumper.slug))

                os.remove(filename)

        if not console:
            with zipfile.ZipFile(zipname, mode='a', allowZip64=True) as z:
                z.writestr('meta.json', json.dumps(meta, indent=4))

        self._print_stats(meta, timing_data)
        self.stdout.write('\nData dumped to file: {}'.format(zipname))

    def _print_stats(self, meta, timing_data):
        self.stdout.ending = '\n'
        for line in format_dump_stats(meta, timing_data):
            self.stdout.write(line)


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise ArgumentTypeError(f'{value!r} is not a positive integer')
    return number


def format_dump_stats(meta, timing_data):
    """Lines of the final dump-stats report: per-model throughput (hours per
    million rows), and per-dumper and grand-total elapsed time.
    """
    lines = [f'{"-" * 32} Dump Stats {"-" * 32}']
    for dumper, models in sorted(meta.items()):
        dumper_timing = timing_data.get(dumper, {})
        lines.append(f"{dumper}: {dumper_timing.get('total', 0):.2f}s")
        model_times = dumper_timing.get('models', {})
        for model, count in sorted(models.items()):
            model_time = model_times.get(model)
            suffix = f'  {format_rate(model_time, count)}' if model_time is not None and count else ''
            lines.append(f'  {model:<50}: {count:>10}{suffix}')
    lines.append('-' * 76)
    total = sum(count for models in meta.values() for count in models.values())
    lines.append(f'Dumped {total} rows')
    grand_total = sum(d.get('total', 0) for d in timing_data.values())
    lines.append(f'Total dump time: {grand_total:.2f}s')
    lines.append('-' * 76)
    return lines


def _get_dump_stream_filename(slug, domain, utcnow, path=None):
    filename = 'dump-{}-{}-{}.gz'.format(slug, domain, utcnow)
    if path:
        return os.path.join(path, filename)
    return filename
