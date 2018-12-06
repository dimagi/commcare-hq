from __future__ import absolute_import
from __future__ import unicode_literals

from django.http import HttpResponse, StreamingHttpResponse, JsonResponse
from io import open
from wsgiref.util import FileWrapper

import json
import logging
import re
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
        # strip all non-alphanumeric chars
        safe_state_name = re.sub('[^0-9a-zA-Z]+', '', self.state_name)
        return 'disha_dump-{}-{}.json'.format(safe_state_name, self.month.strftime('%Y-%m-%d'))

    @memoized
    def _get_file_ref(self):
        return IcdsFile.objects.filter(blob_id=self._blob_id()).first()

    def export_exists(self):
        if self._get_file_ref():
            return True
        else:
            return False

    def get_export_as_http_response(self, stream=False):
        file_ref = self._get_file_ref()
        if file_ref:
            _file = file_ref.get_file_from_blobdb()
            if stream:
                response = StreamingHttpResponse(
                    FileWrapper(_file),
                    content_type='application/json'
                )
                response['Content-Length'] = file_ref.get_file_size()
                return response
            else:
                return HttpResponse(_file.read(), content_type='application/json')
        else:
            return JsonResponse({"message": "Data is not updated for this month"})

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

    def _write_data_in_chunks(self, file_obj):
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
                columns=json.dumps(columns, ensure_ascii=False)).encode('utf8')
        file_obj.write(metadata_line)
        written_count = 0
        num_batches = 10
        for count, (_, end, total, chunk) in enumerate(batch_qs(indicators, num_batches=num_batches)):
            chunk_string = json.dumps(list(chunk), ensure_ascii=False).encode('utf8')
            # chunk is list of lists, so skip enclosing brackets
            file_obj.write(chunk_string[1:-1])
            written_count += len(chunk)
            if written_count != total:
                file_obj.write(",")
            logger.info("Processed {count}/{batches} batches. Total records:{total}".format(
                count=count, total=total, batches=num_batches))
        file_obj.write("]}")

    def build_export_json(self):
        with TransientTempfile() as temp_path:
            with open(temp_path, 'w+b') as f:
                self._write_data_in_chunks(f)
                f.seek(0)
                blob_ref, _ = IcdsFile.objects.get_or_create(blob_id=self._blob_id(), data_type='disha_dumps')
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
