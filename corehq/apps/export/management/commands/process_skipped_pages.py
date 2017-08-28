from __future__ import print_function

import multiprocessing
import os
import shutil
import tempfile
import zipfile

import re
import sh
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError

from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance
from corehq.apps.export.export import _save_export_payload
from corehq.apps.export.management.commands.rebuild_export import (
    SuccessResult, MultithreadedExporter, RetryResult
)
from corehq.util.files import safe_filename


class Command(BaseCommand):
    help = "Remove sensitive columns from an export"

    def add_arguments(self, parser):
        parser.add_argument('export_id')
        parser.add_argument(
            'export_path',
            help='Path to export ZIP',
        )
        parser.add_argument(
            '--processes',
            type=int,
            dest='processes',
            default=multiprocessing.cpu_count() - 1,
            help='Number of parallel processes to run.'
        )
        parser.add_argument(
            '--force-upload',
            action='store_true',
            help='Upload the final archive even if there are still unprocessed pages'
        )

    def handle(self, **options):
        export_id = options.pop('export_id')
        export_archive_path = options.pop('export_path')
        processes = options.pop('processes')
        force_upload = options.pop('force_upload')

        if not os.path.exists(export_archive_path):
            raise CommandError("Export path missing: {}".format(export_archive_path))

        export_instance = get_properly_wrapped_export_instance(export_id)

        extract_to = tempfile.mkdtemp()
        print('Extracting unprocessed pages')
        with zipfile.ZipFile(export_archive_path, 'r') as zipref:
            for member in zipref.namelist():
                if member.startswith('unprocessed'):
                    zipref.extract(member, extract_to)

        unprocessed_path = os.path.join(extract_to, 'unprocessed')
        if not os.path.exists(unprocessed_path):
            print(self.style.ERROR('Export has no unprocessed pages.'))
            shutil.rmtree(extract_to)

        unprocessed_pages = []
        total_docs = 0
        for page_filename in os.listdir(unprocessed_path):
            page_path = os.path.join(unprocessed_path, page_filename)
            page_search = re.search('page_(\d+).json.gz', page_filename)
            if page_search:
                page_number = int(page_search.group(1))
            else:
                raise CommandError('Unexpected page filename: {}'.format(page_filename))

            doc_count = int(sh.wc('-l', page_path).split(' ')[0])
            total_docs += doc_count
            unprocessed_pages.append((page_path, page_number, doc_count))

        export_name = safe_filename(export_instance.name or 'Export')
        if not os.path.exists(os.path.join(extract_to, export_name)):
            os.mkdir(os.path.join(extract_to, export_name))

        if not unprocessed_pages:
            print('No pages left to process')
            return

        print('{} pages still to process'.format(len(unprocessed_pages)))

        exporter = MultithreadedExporter(processes, export_instance, total_docs)
        exporter.start()
        for page_path, page_number, doc_count in unprocessed_pages:
            exporter.process_page(RetryResult(page_number, page_path, doc_count, 0))

        export_results = exporter.get_results(retries_per_page=0)

        successful_pages = [res for res in export_results if isinstance(res, SuccessResult)]
        error_pages = {
            'unprocessed/page_{}.json.gz'.format(res.page)
            for res in export_results if not isinstance(res, SuccessResult)
        }

        final_dir, orig_name = os.path.split(export_archive_path)
        if not error_pages:
            fd, final_path = tempfile.mkstemp()
        else:
            final_name = 'INCOMPLETE_{}_{}.zip'.format(orig_name, datetime.utcnow().isoformat())
            final_path = os.path.join(final_dir, final_name)
        print('Recompiling export')

        with zipfile.ZipFile(final_path, mode='w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as final_zip:
            for result in successful_pages:
                print('  Adding page {} to final file'.format(result.page))
                with zipfile.ZipFile(result.export_path, 'r') as page_file:
                    for path in page_file.namelist():
                        prefix, suffix = path.rsplit('/', 1)
                        final_zip.writestr('{}/{}_{}'.format(
                            prefix, result.page, suffix), page_file.open(path).read()
                        )

            with zipfile.ZipFile(export_archive_path, 'r') as original_export:
                for member in original_export.namelist():
                    if member.startswith(export_name):
                        final_zip.writestr(member, original_export.read(member))
                    elif member in error_pages:
                        final_zip.writestr(member, original_export.read(member))

        if force_upload or not error_pages:
            print('Uploading final archive', '(forced)' if force_upload else '')
            with open(final_path, 'r') as payload:
                _save_export_payload(export_instance, payload)
        if not error_pages:
            os.remove(final_path)
        else:
            print(self.style.ERROR(
                'Not all pages processed successfully.\n'
                'You can re-run the command on the final archive to try again: {}\n'
                'NOTE: final archive not uploaded. '
                'Use --force-upload to upload even with errors'.format(final_path))
            )
        shutil.rmtree(extract_to)
        self.stdout.write(self.style.SUCCESS('Rebuild Complete and payload uploaded'))
