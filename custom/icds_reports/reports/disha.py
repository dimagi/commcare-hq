from __future__ import absolute_import
from __future__ import unicode_literals

from io import open

import json
import logging
from corehq.apps.reports.util import batch_qs
from corehq.util.files import TransientTempfile

from custom.icds_reports.models.aggregate import AwcLocation
from custom.icds_reports.models.views import DishaIndicatorView
from custom.icds_reports.models.helper import IcdsFile
from memoized import memoized


logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')

DISHA_DUMP_EXPIRY = 60 * 60 * 24 * 360  # 1 year


class DishaDump(object):

    def __init__(self, state_name, month):
        self.state_name = state_name
        self.month = month

    def _blob_id(self):
        return 'disha_dump-{}-{}.json'.format(self.state_name.replace(" ", ""), self.month.strftime('%Y-%m-%d'))

    @memoized
    def _get_file_ref(self):
        return IcdsFile.objects.filter(blob_id=self._blob_id()).first()

    def export_exists(self):
        if self._get_file_ref():
            return True
        else:
            return False

    def get_json_export(self):
        file_ref = self._get_file_ref()
        if file_ref:
            return file_ref.get_file_from_blobdb().read()
        else:
            return ""

    def _get_columns(self):
        columns = [field.name for field in DishaIndicatorView._meta.fields]
        columns.remove("month")
        return columns

    def _get_rows(self):
        return DishaIndicatorView.objects.filter(
            month=self.month,
            state_name__iexact=self.state_name
            # batch_qs requires ordered queryset
        ).order_by('pk').values_list(*self._get_columns())

    def _write_data_in_chunks(self, temp_path):
        # Writes indicators in json format to the file at temp_path
        #   in chunks so as to avoid memory errors while doing json.dumps.
        #   The structure of the json is as below
        #   {
        #       'month': '2018-09-01',
        #       'state_name': 'Andhra Pradesh',
        #       'columns': [<List of disha columns>],
        #       'rows': List of lists of rows, in the same order as columns
        #   }
        columns = self._get_columns()
        indicators = self._get_rows()
        metadata_line = '{{'\
            '"month":"{month}", '\
            '"state_name": "{state_name}", '\
            '"column_names": {columns}, '\
            '"rows": ['.format(
                month=self.month,
                state_name=self.state_name,
                columns=json.dumps(columns, ensure_ascii=False))
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(metadata_line)
            written_count = 0
            for _, end, total, chunk in batch_qs(indicators, num_batches=10):
                chunk_string = json.dumps(list(chunk), ensure_ascii=False)
                # chunk is list of lists, so skip enclosing brackets
                f.write(chunk_string[1:-1])
                written_count += len(chunk)
                if written_count != total:
                    f.write(",")
                logger.info("Processed {end}/{total} records".format(end=end, total=total))
            f.write("]}")

    def build_export_json(self):
        with TransientTempfile() as temp_path:
            self._write_data_in_chunks(temp_path)
            with open(temp_path, 'r', encoding='utf-8') as f:
                blob_ref, _ = IcdsFile.objects.get_or_create(blob_id='sd', data_type='disha_dumps')
                blob_ref.store_file_in_blobdb(f, expired=1)
                blob_ref.save()


def build_dumps_for_month(month, rebuild=False):
    states = AwcLocation.objects.values_list('state_name', flat=True).distinct()

    for state_name in states:
        dump = DishaDump(state_name, month)
        if dump.export_exists() and not rebuild:
            logger.info("Skipping, export is already generated for state {}".format(state_name))
        else:
            logger.info("Generating for state {}".format(state_name))
            dump.build_export_json()
            logger.info("Finished for state {}".format(state_name))
