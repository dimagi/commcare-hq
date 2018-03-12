from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
import csv
import os
import shutil
import tempfile
import zipfile

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

        is_zip = False
        deid_root = None
        export_name = None
        if os.path.isfile(path):
            print('Extracting export')
            is_zip = True
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
                if page.endswith('csv')
            ]

            deid_root = tempfile.mkdtemp()
            deid_subdir = os.path.join(deid_root, export_name)
            os.mkdir(deid_subdir)
        else:
            print('Export already extracted')
            extract_to = path
            export_pages = [
                (os.path.join(extract_to, page), page)
                for page in os.listdir(extract_to)
                if page.endswith('csv')
            ]

            deid_subdir = os.path.join(extract_to, 'deid')
            os.mkdir(deid_subdir)

        for page in export_pages:
            cols_to_keep = _get_columns_to_keep(page[0], columns)
            dest = os.path.join(deid_subdir, page[1])
            if not cols_to_keep:
                shutil.copyfile(page[0], dest)
                print ('  Skipping file: {}, as it doesnt have deid columns'.format(page[1]))
                continue
            print('  Processing file: {}'.format(page[1]))
            _trim_csv_columns(page[0], dest, cols_to_keep)

        if is_zip:
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
        else:
            print("Deidentifed exports writen to {}".format(deid_subdir))


def _trim_csv_columns(path, dest, cols_to_keep):
    with open(path, 'rb') as source:
        rdr = csv.reader(source)
        with open(dest, "wb") as result:
            wtr = csv.writer(result)
            for r in rdr:
                wtr.writerow([r[i] for i in cols_to_keep])


def _get_headers(path):
    with open(path, 'r') as sample_file:
        return sample_file.readline().strip()


def _get_columns_to_keep(path, deid_columns):
    headers_line = _get_headers(path)
    headers = headers_line.strip().split(',')
    return [index for index, header in enumerate(headers) if header not in deid_columns]
