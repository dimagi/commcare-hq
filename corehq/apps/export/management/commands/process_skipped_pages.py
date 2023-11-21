import multiprocessing
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

import sh

from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance
from corehq.apps.export.multiprocess import (
    UNPROCESSED_PAGES_DIR,
    MultiprocessExporter,
    RetryResult,
    _add_compressed_page_to_zip,
)
from corehq.util.files import safe_filename


class Command(BaseCommand):
    help = "Remove sensitive columns from an export"

    def add_arguments(self, parser):
        parser.add_argument('export_id')
        parser.add_argument(
            '--export_path',
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
        if __debug__:
            raise CommandError("You should run this with 'python -O'")

        export_id = options.pop('export_id')
        export_archive_path = options.pop('export_path')
        processes = options.pop('processes')
        force_upload = options.pop('force_upload')

        export_instance = get_properly_wrapped_export_instance(export_id)

        if not export_archive_path or not os.path.exists(export_archive_path):
            confirm = input(
                """
                No export archive provided. Do you want to download the latest one? [y/N]
                """
            )
            if not confirm == "y":
                raise CommandError("Export path missing: {}".format(export_archive_path))

            export_archive_path = self._download_export(export_instance)

        extract_to = tempfile.mkdtemp()
        total_docs, unprocessed_pages = self._get_unprocessed_pages(export_archive_path, extract_to)

        print('{} pages still to process'.format(len(unprocessed_pages)))

        exporter = MultiprocessExporter(export_instance, total_docs, processes)
        error_pages, successful_pages = self._process_pages(
            exporter, unprocessed_pages
        )

        final_path = self.compile_final_zip(
            error_pages, export_archive_path, export_instance, successful_pages
        )

        if force_upload or not error_pages:
            print('Uploading final archive', '(forced)' if force_upload and error_pages else '')
            exporter.upload(final_path, clean=not error_pages)
        else:
            print(self.style.ERROR(
                'Not all pages processed successfully.\n'
                'You can re-run the command on the final archive to try again: {}\n'
                'NOTE: final archive not uploaded. '
                'Use --force-upload to upload even with errors'.format(final_path))
            )
        shutil.rmtree(extract_to)
        self.stdout.write(self.style.SUCCESS('Rebuild Complete and payload uploaded'))

    def _download_export(self, export_instance):
        export_archive_path = '{}_{}.zip'.format(
            safe_filename(export_instance.name or 'Export'),
            datetime.utcnow().isoformat()
        )
        payload = export_instance.get_payload(stream=True)
        with open(export_archive_path, 'wb') as download:
            shutil.copyfileobj(payload, download)
        return export_archive_path

    def compile_final_zip(self, error_pages, export_archive_path, export_instance, successful_pages):
        final_dir, orig_name = os.path.split(export_archive_path)
        if not error_pages:
            fd, final_path = tempfile.mkstemp()
            os.close(fd)
        else:
            final_name = 'INCOMPLETE_{}_{}.zip'.format(orig_name, datetime.utcnow().isoformat())
            final_path = os.path.join(final_dir, final_name)
        print('Recompiling export')
        export_name = safe_filename(export_instance.name or 'Export')
        with zipfile.ZipFile(final_path, mode='w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as final_zip:
            for result in successful_pages:
                print('  Adding page {} to final file'.format(result.page))
                _add_compressed_page_to_zip(final_zip, result.page, result.path)

            print('  Adding original export pages and unprocessed pages final file')

            def _include_member(member):
                # add original export pages and any raw data that we weren't able to process
                add = member.startswith(export_name) or member in error_pages
                if add:
                    print('    {}'.format(member))
                return add

            _copy_files_from_zip_to_zip(final_zip, export_archive_path, _include_member)
        return final_path

    def _process_pages(self, exporter, unprocessed_pages):
        exporter.start()
        for page_path, page_number, doc_count in unprocessed_pages:
            exporter.process_page(RetryResult(page_number, page_path, doc_count, 0))
        export_results = exporter.get_results(retries_per_page=0)
        successful_pages = [res for res in export_results if res.success]
        error_pages = {
            '{}/page_{}.json.gz'.format(UNPROCESSED_PAGES_DIR, res.page)
            for res in export_results if not res.success
        }
        return error_pages, successful_pages

    def _get_unprocessed_pages(self, export_archive_path, extract_to_path):
        print('Extracting unprocessed pages')
        with zipfile.ZipFile(export_archive_path, 'r') as zipref:
            for member in zipref.namelist():
                if member.startswith(UNPROCESSED_PAGES_DIR):
                    zipref.extract(member, extract_to_path)

        unprocessed_path = os.path.join(extract_to_path, UNPROCESSED_PAGES_DIR)
        if not os.path.exists(unprocessed_path):
            shutil.rmtree(extract_to_path)
            raise CommandError('Export has no unprocessed pages.')

        unprocessed_pages = []
        total_docs = 0
        for page_filename in os.listdir(unprocessed_path):
            page_path = os.path.join(unprocessed_path, page_filename)
            page_search = re.search(r'page_(\d+).json.gz', page_filename)
            if page_search:
                page_number = int(page_search.group(1))
            else:
                raise CommandError('Unexpected page filename: {}'.format(page_filename))

            doc_count = int(sh.wc('-l', page_path).strip().split(' ')[0])
            total_docs += doc_count
            unprocessed_pages.append((page_path, page_number, doc_count))

        if not unprocessed_pages:
            raise CommandError('No pages left to process')

        return total_docs, unprocessed_pages


def _copy_files_from_zip_to_zip(to_zip, from_zip_path, include_filter=None):
    with zipfile.ZipFile(from_zip_path, 'r') as from_zip:
        for member in from_zip.namelist():
            if not include_filter or include_filter(member):
                to_zip.writestr(member, from_zip.read(member))
