import datetime
import logging
import os
import sys

from django.core.management import BaseCommand, CommandError

from corehq.blobs.export import BlobExporter, DEFAULT_CONCURRENCY, PROGRESS_INTERVAL
from corehq.util.decorators import change_log_level

USAGE = "Usage: ./manage.py run_blob_export [options] <domain>"
BOTOCORE_DEFAULT_POOL_SIZE = 10  # botocore's default max_pool_connections


class Command(BaseCommand):
    """
    Example: ./manage.py run_blob_export [options] domain

    Dump XForms in parallel:
        ./manage.py run_blob_export --limit-to-db p0 domain
         ...
        ./manage.py run_blob_export --limit-to-db pN domain

    To top-up an older blob dump, first extract a list of names from the archive:
        $ tar --list -f blob_export.tar.gz > blob_export.list
    Then provide this file to the `--already_exported` argument to skip over
    those objects in this dump.
    """
    help = USAGE

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--dir',
            dest='dir',
            help="Optionally specify a directory to write the file to. "
                 "The directory will be created if it does not exist.",
        )
        parser.add_argument('--progress-interval', type=int, default=PROGRESS_INTERVAL,
                            help='Print a progress line (with throughput) every N objects '
                                 f'processed (default: {PROGRESS_INTERVAL}).')
        parser.add_argument('--limit-to-db', dest='limit_to_db',
                            help="When specifying a SQL importer use this to restrict "
                                 "the exporter to a single database.")
        parser.add_argument('--already_exported', dest='already_exported',
                            help='Pass a file with a list of blob names already exported')
        parser.add_argument(
            '--concurrency', type=int, default=DEFAULT_CONCURRENCY,
            help="Number of blobs to fetch from S3 in parallel (default: "
                 f"{DEFAULT_CONCURRENCY}). Values above botocore's default "
                 f"connection-pool size ({BOTOCORE_DEFAULT_POOL_SIZE}) raise "
                 "max_pool_connections to match, so the extra connections are "
                 "reused rather than opened and discarded each request.",
        )

    @change_log_level('boto3', logging.WARNING)
    @change_log_level('botocore', logging.WARNING)
    def handle(
        self,
        domain=None,
        dir=None,
        reset=False,
        progress_interval=PROGRESS_INTERVAL,
        limit_to_db=None,
        concurrency=DEFAULT_CONCURRENCY,
        **options,
    ):
        already_exported = get_lines_from_file(options['already_exported'])
        print(f"Found {len(already_exported)} existing blobs, these will be skipped")

        if not domain:
            raise CommandError(USAGE)

        if dir:
            os.makedirs(dir, exist_ok=True)

        self.stdout.write(f"\nRunning blob exporter\n{'-' * 50}")
        export_filename = _get_export_filename(
            domain, already_exported, path=dir, limited_to_db=limit_to_db
        )
        if os.path.exists(export_filename):
            raise CommandError(
                f"Export file '{export_filename}' exists. Remove the file and re-run the command."
            )

        _ensure_s3_pool_size(concurrency)
        exporter = BlobExporter(domain)
        total, skips = exporter.migrate(
            export_filename,
            progress_interval=progress_interval,
            limit_to_db=limit_to_db,
            already_exported=already_exported,
            concurrency=concurrency,
        )
        self.stdout.write(f'\nData dumped to file: {export_filename}')
        if skips:
            sys.exit(skips)


def _ensure_s3_pool_size(concurrency):
    """Raise botocore's connection pool to serve ``concurrency`` parallel fetches.

    The pool defaults to ``BOTOCORE_DEFAULT_POOL_SIZE``. botocore doesn't block
    when it's exceeded; it opens connections beyond the pool and discards them
    after use, so a higher ``--concurrency`` would otherwise churn connections
    (new TLS handshake per excess fetch). Must run before the blob db client is
    built (i.e. before the first ``get_blob_db()`` call).
    """
    from django.conf import settings
    for key in ('S3_BLOB_DB_SETTINGS', 'OLD_S3_BLOB_DB_SETTINGS'):
        s3_settings = getattr(settings, key, None)
        if not s3_settings:
            continue
        config = s3_settings.get('config') or {}
        if concurrency > config.get('max_pool_connections', BOTOCORE_DEFAULT_POOL_SIZE):
            config['max_pool_connections'] = concurrency
            s3_settings['config'] = config


def get_lines_from_file(filename):
    if not filename:
        return set()
    with open(filename) as f:
        return {line.strip() for line in f}


def _get_export_filename(domain, already_exported, path=None, limited_to_db=None):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H.%M')
    part = '-part' if already_exported else ''
    db = f'-{limited_to_db}' if limited_to_db else ''
    filename = f'{timestamp}-{domain}-blobs{part}{db}.tar.gz'
    if path:
        return os.path.join(path, filename)
    return filename
