from __future__ import absolute_import
from __future__ import print_function

from __future__ import unicode_literals
import logging
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime

import multiprocessing
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from corehq.apps.export.const import FORM_EXPORT
from corehq.apps.export.dbaccessors import get_properly_wrapped_export_instance
from corehq.apps.export.export import get_export_size
from corehq.apps.export.filters import TermFilter, NOT
from corehq.apps.export.forms import FormExportFilterBuilder
from corehq.apps.export.models import MAIN_TABLE, PathNode
from corehq.apps.export.multiprocess import MultiprocessExporter, OutputPaginator, run_multiprocess_exporter
from corehq.util.files import safe_filename
from dimagi.utils.parsing import string_to_utc_datetime

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Rebuild a saved export using multiple processes"

    def add_arguments(self, parser):
        parser.add_argument('export_id')
        parser.add_argument('-d', '--download_path', help="Path to download export to.")
        parser.add_argument(
            '--processes',
            type=int,
            dest='processes',
            default=multiprocessing.cpu_count() - 1,
            help='Number of parallel processes to run.'
        )

    def handle(self, export_id, **options):
        export_instance = get_properly_wrapped_export_instance(export_id)

        if export_instance.type != FORM_EXPORT:
            raise CommandError("Unsupported export type: %s" % export_instance.type)

        filters = export_instance.get_filters()
        if any(isinstance(filter_, FormExportFilterBuilder.date_filter_class) for filter_ in filters):
            raise CommandError("Export already has a date filter and so must be fully rebuilt.")

        export_archive_path = download_export(export_instance, download_path=options.get('download_path'))
        last_run_meta = get_last_run_meta(export_instance, export_archive_path)
        last_form_id, last_form_received_on, last_page_number = last_run_meta

        print("Exporting data since '%s'" % last_form_received_on)
        filters.append(FormExportFilterBuilder.date_filter_class(gt=last_form_received_on))
        if last_form_id:
            filters.append(NOT(TermFilter('_id', last_form_id)))
        total_docs = get_export_size(export_instance, filters)
        exporter = MultiprocessExporter(
            export_instance, total_docs, options['processes'],
            existing_archive_path=options['download_path'], keep_file=True
        )
        paginator = OutputPaginator(export_id, last_page_number + 1)

        logger.info('Starting data dump of {} docs'.format(total_docs))
        run_multiprocess_exporter(exporter, filters, paginator, 1000000)


def get_last_run_meta(export_instance, export_archive_path):
    main_table = export_instance.get_table(MAIN_TABLE)
    received_on_column_index, received_on_column = main_table.get_column([PathNode(name="received_on")],
                                                                         'ExportItem', None)
    if not received_on_column:
        raise CommandError("Export does not contain a field appropriate for finding the last exported date.")
    form_id_column_index, form_id_column = main_table.get_column(
        [
            PathNode(name='form'),
            PathNode(name='meta'),
            PathNode(name='instanceID')
        ], 'ExportItem', None
    )
    if form_id_column_index is None:
        print("WARNING: unable to get last form ID. Export may contain a duplicate form")

    last_page_path = _get_last_page(export_archive_path, main_table.label)
    if last_page_path:
        folder, filename = last_page_path.rsplit('/', 1)
        matcher = re.match(r'(\d+)_.*', filename)
        last_page_number = int(matcher.group(1))
    else:
        last_page_number = 0
    last_form_id, date_col_string = _get_column_value_from_last_line(
        last_page_path, form_id_column_index, received_on_column_index
    )
    last_form_received_on = string_to_utc_datetime(date_col_string)
    return (
        last_form_id,
        last_form_received_on,
        last_page_number
    )


def _get_column_value_from_last_line(page_path, form_id_index, date_index):
    last_line = _get_last_line(page_path)
    fields = last_line.strip().split(',')
    return fields[form_id_index] if form_id_index is not None else None, fields[date_index]


def _get_last_page(export_archive_path, table_label):
    extract_to = tempfile.mkdtemp()
    with zipfile.ZipFile(export_archive_path, 'r') as zipref:
        # skip first since that will be page 0
        for member in sorted(zipref.namelist(), reverse=True)[1:5]:
            folder, filename = member.rsplit('/', 1)
            if re.match(r'(\d+_)?%s.csv' % table_label, filename):
                zipref.extract(member, extract_to)
                return os.path.join(extract_to, member)


def _get_last_line(file_path):
    """
    https://stackoverflow.com/a/18603065/632517
    """
    with open(file_path, "rb") as f:
        f.seek(-2, os.SEEK_END)  # Jump to the second last byte.
        while f.read(1) != b"\n":  # Until EOL is found...
            f.seek(-2, os.SEEK_CUR)  # ...jump back the read byte plus one more.
        return f.readline()


def download_export(export_instance, download_path=None):
    if not download_path:
        export_archive_path = '{}_{}.zip'.format(
            safe_filename(export_instance.name.encode('ascii', 'replace') or 'Export'),
            datetime.utcnow().isoformat()
        )
        download_path = os.path.join(settings.SHARED_DRIVE_ROOT, export_archive_path)
    if not os.path.exists(download_path):
        payload = export_instance.get_payload(stream=True)
        with open(download_path, 'w') as download:
            shutil.copyfileobj(payload, download)
    return download_path
