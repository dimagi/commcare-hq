from __future__ import print_function

import os
import shutil
import tempfile
import zipfile

import sh
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Remove sensitive columns from an export"

    def add_arguments(self, parser):
        parser.add_argument(
            'export_path',
            help='Path to export ZIP',
        )
        parser.add_argument(
            'columns',
            metavar='C',
            nargs='+',
            help='Column names to remove',
        )

    def handle(self, **options):
        path = options.pop('export_path')
        columns = options.pop('columns')

        if not os.path.exists(path):
            raise CommandError("Export path missing: {}".format(path))

        print('Extracting export')
        extract_to = tempfile.mkdtemp()
        zip_ref = zipfile.ZipFile(path, 'r')
        zip_ref.extractall(extract_to)
        zip_ref.close()

        subdirs = [sub for sub in os.listdir(extract_to) if os.path.isdir(os.path.join(extract_to, sub))]
        if not len(subdirs) == 1:
            raise CommandError('Expected only one subdirectory: {}'.format(','.join(subdirs)))

        export_name = subdirs[0]
        export_pages = [
            (os.path.join(extract_to, export_name, page), page)
            for page in os.listdir(os.path.join(extract_to, export_name))
        ]
        headers_line = self._get_headers(export_pages)
        headers = headers_line.strip().split(',')
        deid_indexes = ','.join([str(headers.index(col) + 1) for col in columns])

        deid_root = tempfile.mkdtemp()
        deid_subdir = os.path.join(deid_root, export_name)
        os.mkdir(deid_subdir)

        cut = sh.cut.bake('-d,', '-f{}'.format(deid_indexes), '--complement')
        for page in export_pages:
            print('  Processing file: {}'.format(page[1]))
            dest = os.path.join(deid_subdir, page[1])
            cut(page[0], _out=dest)

        final_dir, orig_name = os.path.split(path)
        final_name = 'DEID_{}'.format(orig_name)
        final_path = os.path.join(final_dir, final_name)
        print('Recompiling export to {}'.format(final_path))
        with zipfile.ZipFile(final_path, mode='w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            for page in export_pages:
                dest = os.path.join(deid_subdir, page[1])
                z.write(dest, '{}/{}'.format(export_name, page[1]))

        shutil.rmtree(extract_to)
        shutil.rmtree(deid_root)

    def _get_headers(self, page_paths):
        def __first_line(path):
            with open(path, 'r') as sample_file:
                return sample_file.readline().strip()

        headers = __first_line(page_paths[0][0])

        for page in page_paths[1:]:
            page_headers = __first_line(page[0])
            if not page_headers == headers:
                raise CommandError("Headers for page {} don't match".format(page[1]))

        return headers
