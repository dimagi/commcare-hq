import datetime
import gzip
import inspect
import json
import logging
import os
import re
import zipfile
from collections import namedtuple
from concurrent import futures
from pathlib import Path

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
        parser.add_argument('--use-extracted', action='store_true', default=False, dest='use_extracted',
                            help="Use already extracted dump if it exists.")
        parser.add_argument('--output-path', help='Directory to write data files to.')
        parser.add_argument('--json-output', action="store_true", help="Produce JSON output for use in tests")

    @change_log_level('boto3', logging.WARNING)
    @change_log_level('botocore', logging.WARNING)
    def handle(self, path, **options):
        use_extracted = options.get('use_extracted')
        output_path = options.get('output_path') or ''

        already_exported = get_lines_from_file(options['already_exported'])
        if already_exported:
            print("Found {} existing blobs, these will be skipped".format(len(already_exported)))

        if output_path and (not os.path.exists(output_path) or os.path.isfile(output_path)):
            raise CommandError("Output path must exist and be a folder.")

        filter_pattern = options.get('meta-file-filter')
        filter_rx = None
        if filter_pattern:
            filter_rx = re.compile(filter_pattern)

        def _filter(filename):
            return 'blob_meta' in filename and (not filter_rx or filter_rx.match(filename))

        target_dir = get_tmp_extract_dir(path, specifier='blob_meta')
        target_path = Path(target_dir)
        export_meta_files = []
        if not target_path.exists():
            with zipfile.ZipFile(path, 'r') as archive:
                archive.extract('meta.json', target_dir)
                for dump_file in archive.namelist():
                    if 'blob_meta' in dump_file:
                        archive.extract(dump_file, target_dir)
        elif not use_extracted:
            raise CommandError(
                "Extracted dump already exists at {}. Delete it or use --use-extracted".format(target_dir))

        meta = json.loads(target_path.joinpath('meta.json').read_text())
        for file in target_path.iterdir():
            if _filter(file.name):
                export_meta_files.append(file)

        results = []
        filenames = []
        with futures.ThreadPoolExecutor(max_workers=len(export_meta_files)) as executor:
            for path in export_meta_files:
                results.append(executor.submit(_export_blobs, output_path, path, meta))

            for result in futures.as_completed(results):
                filenames.append(result.result())

        if options.get("json_output"):
            return json.dumps({"paths": filenames})


def _export_blobs(output_path, path, meta):
    export_filename = os.path.join(output_path, _get_export_filename(path))
    migrator = BlobDbBackendExporter(export_filename, None)
    with migrator:
        expected_count = meta[path.stem]["blobs.BlobMeta"]
        prefix = f"Exporting from {path.name}"
        for obj in with_progress_bar(_key_iterator(path), length=expected_count, prefix=prefix, oneline=False):
            migrator.process_object(obj)

    return export_filename


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


def _get_export_filename(meta_path):
    meta_filename = os.path.splitext(os.path.basename(meta_path))[0]
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H.%M')
    return f'{meta_filename}-blobs-{timestamp}.tar.gz'
