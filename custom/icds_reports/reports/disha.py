from __future__ import absolute_import
from __future__ import unicode_literals

from django.core.serializers.json import DjangoJSONEncoder
from io import BytesIO

import json

from custom.icds_reports.models.views import DishaIndicatorView
from custom.icds_reports.models.helper import IcdsFile


class DishaDump(object):

    def __init__(self, state_name, month):
        self.state_name = state_name
        self.month = month

    def _blob_id(self):
        return 'disha_dump-{}-{}.json'.format(self.state_name, self.month.strftime('%Y-%m-%d'))

    def get_data(self):
        dump = IcdsFile.objects.filter(blob_id=self._blob_id()).first()
        if dump:
            return dump.get_file_from_blobdb().read()
        else:
            return ""

    def build(self):
        columns = [field.name for field in DishaIndicatorView._meta.fields]
        columns.remove("month")
        indicators = DishaIndicatorView.objects.filter(
            month=self.month,
            state_name__iexact=self.state_name
        ).values_list(*columns)
        data = {
            "month": str(self.month),
            "state_name": self.state_name,
            "column_names": columns,
            "rows": list(indicators)
        }
        file = BytesIO(json.dumps(data, cls=DjangoJSONEncoder))
        blob_ref = IcdsFile.objects.get_or_create(blob_id=self._blob_id(), data_type='disha_dumps')
        blob_ref.store_file_in_blobdb(file)
        blob_ref.save()
