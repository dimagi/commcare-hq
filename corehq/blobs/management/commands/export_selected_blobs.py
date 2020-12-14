import datetime
import gzip
import inspect
import json
import logging
import os
import pathlib
import re
import shutil
import zipfile
from collections import namedtuple
from pathlib import Path

import atexit
from django.core.management import BaseCommand, CommandError

from corehq.apps.dump_reload.management.commands.load_domain_data import get_tmp_extract_dir
from corehq.blobs.export import BlobDbBackendExporter
from corehq.blobs.management.commands.run_blob_export import get_lines_from_file
from corehq.util.decorators import change_log_level
from corehq.util.log import with_progress_bar

BlobMetaKey = namedtuple('BlobMetaKey', 'key')


class Command(BaseCommand):
    help = inspect.cleandoc("""
    Usage ./manage.py export_selected_blobs [options] path_to_export_zip

    'path_to_export_zip' must be a ZIP file generated using `dump_domain_data` and must
    include a `meta.json` file with the object counts.

    To top-up an older blob dump, first extract a list of names from the archive:
        $ tar --list -f blob_export.tar.gz > blob_export.list
    Then provide this file to the `--already_exported` argument to skip over
    those objects in this dump.
    """)

    def add_arguments(self, parser):
        parser.add_argument('path', help='Path to a file with a list of blob meta JSON to export')
        parser.add_argument('--meta-file-filter', nargs='?',
                            help='Only export blobs for metadata in files with filenames matching the filter regex.')
        parser.add_argument('--already_exported', dest='already_exported',
                            help='Pass a file with a list of blob names already exported')
        parser.add_argument('--json-output', action="store_true", help="Produce JSON output for use in tests")

    @change_log_level('boto3', logging.WARNING)
    @change_log_level('botocore', logging.WARNING)
    def handle(self, path, **options):
        already_exported = get_lines_from_file(options['already_exported'])
        print("Found {} existing blobs, these will be skipped".format(len(already_exported)))

        filter_pattern = options.get('meta-file-filter')
        filter_rx = None
        if filter_pattern:
            filter_rx = re.compile(filter_pattern)

        def _filter(filename):
            return 'blob_meta' in filename and (not filter_rx or filter_rx.match(filename))

        target_dir = get_tmp_extract_dir(path, specifier='blob_meta')
        atexit.register(lambda: shutil.rmtree(target_dir))

        target_path = Path(target_dir)
        export_meta_files = []
        with zipfile.ZipFile(path, 'r') as archive:
            meta = json.loads(archive.read("meta.json"))
            for dump_file in archive.namelist():
                if _filter(dump_file):
                    export_meta_files.append(target_path.joinpath(dump_file))
                    if not target_path.joinpath(dump_file).exists():
                        archive.extract(dump_file, target_dir)

        export_filename = _get_export_filename(path, already_exported)
        if os.path.exists(export_filename):
            raise CommandError(f"Export file '{export_filename}' exists. "
                               f"Remove the file and re-run the command.")

        migrator = BlobDbBackendExporter(export_filename, already_exported)
        with migrator:
            for path in export_meta_files:
                expected_count = meta[path.stem]["blobs.BlobMeta"]
                prefix = f"Exporting from {path.name}"
                for obj in with_progress_bar(_key_iterator(path), length=expected_count, prefix=prefix):
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

    if '.gz' in path.suffixes:
        try:
            with gzip.open(path, 'r') as f:
                yield from _get_keys(f)
            return
        except gzip.BadGzipFile:
            pass

    with path.open(mode='r') as f:
        yield from _get_keys(f)


def _get_export_filename(meta_path, already_exported):
    meta_filename = os.path.splitext(os.path.basename(meta_path))[0]
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H.%M')
    part = '-part' if already_exported else ''
    return f'{meta_filename}-blobs-{timestamp}-{part}.tar.gz'
