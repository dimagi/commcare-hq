from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import datetime
from django.http import JsonResponse
from io import open

import json
import logging
import re
from corehq.util.download import get_download_response
from corehq.util.files import TransientTempfile
from corehq.util.sentry import is_pg_cancelled_query_exception
from couchexport.export import Format

from custom.icds_reports.const import AggregationLevels
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
        # This will be the reference to the blob, if this is updated
        #   attention should be paid to the old blobs whose references
        #   might be lost.
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

    def get_export_as_http_response(self, request):
        file_ref = self._get_file_ref()
        if file_ref:
            _file = file_ref.get_file_from_blobdb()
            content_format = Format('', 'json', '', True)
            return get_download_response(_file, file_ref.get_file_size(), content_format, self._blob_id(), request)
        else:
            from custom.icds_reports.tasks import build_missing_disha_dump
            args = [self.month, self.state_name]
            now = datetime.utcnow()
            if now.hour >= 14:
                # 14 hours should be when much after ICDS agg task would have finished by
                build_missing_disha_dump.delay(*args)
            else:
                build_missing_disha_dump.apply_async(
                    args=args,
                    eta=now.replace(hour=14)
                )
            return JsonResponse({"message": "Data is not updated for this month, please check after 14:00 UTC"})

    def _get_columns(self):
        columns = [field.name for field in DishaIndicatorView._meta.fields]
        columns.remove("month")
        return columns

    def _get_rows(self, query_master=False):
        if query_master:
            objects = DishaIndicatorView.objects.using('icds-ucr')
        else:
            objects = DishaIndicatorView.objects
        return objects.filter(
            month=self.month,
            state_name__iexact=self.state_name
        ).values_list(*self._get_columns())

    def _write_data(self, file_obj, query_master=False):
        # Writes indicators in json format to the file at temp_path
        #   The structure of the json is as below
        #   {
        #       'month': '2018-09-01',
        #       'state_name': 'Andhra Pradesh',
        #       'columns': [<List of disha columns>],
        #       'rows': List of lists of rows, in the same order as columns
        #   }
        data = {
            'month': str(self.month),
            'state_name': self.state_name,
            'column_names': self._get_columns(),
            'rows': list(self._get_rows(query_master))
        }
        file_obj.write(json.dumps(data, ensure_ascii=False).encode('utf8'))

    def build_export_json(self, query_master=False):
        with TransientTempfile() as temp_path:
            with open(temp_path, 'w+b') as f:
                self._write_data(f, query_master)
                f.seek(0)
                blob_ref, _ = IcdsFile.objects.get_or_create(blob_id=self._blob_id(), data_type='disha_dumps')
                blob_ref.store_file_in_blobdb(f, expired=DISHA_DUMP_EXPIRY)
                blob_ref.save()


def build_dumps_for_month(month, rebuild=False):
    states = AwcLocation.objects.filter(aggregation_level=AggregationLevels.STATE, state_is_test=0).values_list('state_name', flat=True)
    for state_name in states:
        dump = DishaDump(state_name, month)
        if not rebuild and dump.export_exists():
            logger.info("Skipping, export is already generated for state {}".format(state_name))
        else:
            logger.info("Generating for state {}".format(state_name))
            MAX_RETRY_COUNT = 5
            retry_count = 0
            while True:
                try:
                    # force query to master after max retries
                    query_master = retry_count == MAX_RETRY_COUNT
                    dump.build_export_json(query_master=query_master)
                except Exception as e:
                    # The DISHA sql query that runs on aggregate tables can be cancelled by Postgres
                    #   if the query is routed to standby and that standby needs to alter the matching rows
                    if not is_pg_cancelled_query_exception(e):
                        raise e
                    else:
                        retry_count += 1
                        logger.info("Postgres cancelled the DISHA query. Retry count: {}/{}".format(
                            str(retry_count), str(MAX_RETRY_COUNT)))
                else:
                    break
            logger.info("Finished for state {}".format(state_name))
