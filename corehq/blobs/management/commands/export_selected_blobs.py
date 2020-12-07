import datetime
import gzip
import inspect
import json
import logging
import os
import pathlib
from collections import namedtuple

from django.core.management import BaseCommand, CommandError

from corehq.blobs.export import BlobDbBackendExporter
from corehq.blobs.management.commands.run_blob_export import get_lines_from_file
from corehq.util.decorators import change_log_level

BlobMetaKey = namedtuple('BlobMetaKey', 'key')


class Command(BaseCommand):
    help = inspect.cleandoc("""
    Usage ./manage.py export_selected_blobs [options] path_to_blob_meta

    'path_to_blob_meta' may be a gzip file or a plain text file containing a single JSON
    representation of the BlobMeta class per line. Use `dump_domain_data` to generate
    the file.

    To top-up an older blob dump, first extract a list of names from the archive:
        $ tar --list -f blob_export.tar.gz > blob_export.list
    Then provide this file to the `--already_exported` argument to skip over
    those objects in this dump.
    """)

    def add_arguments(self, parser):
        parser.add_argument('path', help='Path to a file with a list of blob meta JSON to export')
        parser.add_argument('--already_exported', dest='already_exported',
                            help='Pass a file with a list of blob names already exported')
        parser.add_argument('--json-output', action="store_true", help="Produce JSON output for use in tests")

    @change_log_level('boto3', logging.WARNING)
    @change_log_level('botocore', logging.WARNING)
    def handle(self, path, **options):
        already_exported = get_lines_from_file(options['already_exported'])
        print("Found {} existing blobs, these will be skipped".format(len(already_exported)))

        export_filename = _get_export_filename(path, already_exported)
        if os.path.exists(export_filename):
            raise CommandError(f"Export file '{export_filename}' exists. "
                               f"Remove the file and re-run the command.")

        migrator = BlobDbBackendExporter(export_filename, already_exported)
        with migrator:
            for obj in _key_iterator(path):
                migrator.process_object(obj)
                if migrator.total_blobs % 1000 == 0:
                    print("Processed {} objects".format(migrator.total_blobs))

        print("Exported {} objects to {}".format(migrator.total_blobs, export_filename))
        if options.get("json_output"):
            return json.dumps({"path": export_filename})


def _key_iterator(path):
    def _get_keys(iterator):
        for line in iterator:
            if line.strip():
                obj = json.loads(line)
                yield BlobMetaKey(obj['fields']['key'])

    if '.gz' in pathlib.Path(path).suffixes:
        try:
            with gzip.open(path, 'r') as f:
                yield from _get_keys(f)
            return
        except gzip.BadGzipFile:
            pass

    with open(path, 'r') as f:
        yield from _get_keys(f)


def _get_export_filename(meta_path, already_exported):
    meta_filename = os.path.splitext(os.path.basename(meta_path))[0]
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H.%M')
    part = '-part' if already_exported else ''
    return f'{meta_filename}-blobs-{timestamp}-{part}.tar.gz'
