from __future__ import absolute_import
from __future__ import unicode_literals
from dimagi.ext.couchdbkit import *
from memoized import memoized
import six

from corehq.util.python_compatibility import soft_assert_type_text


class WisePillDeviceEvent(Document):
    """
    One DeviceEvent is created each time a device sends data that is 
    forwarded to the CommCareHQ WisePill API (/wisepill/device/).
    """
    domain = StringProperty()
    data = StringProperty()
    received_on = DateTimeProperty()
    case_id = StringProperty() # Document _id of the case representing the device that sent this data in
    processed = BooleanProperty()

    @property
    @memoized
    def data_as_dict(self):
        """
        Convert 'a=b,c=d' to {'a': 'b', 'c': 'd'}
        """
        result = {}
        if isinstance(self.data, six.string_types):
            soft_assert_type_text(self.data)
            items = self.data.strip().split(',')
            for item in items:
                parts = item.partition('=')
                key = parts[0].strip().upper()
                value = parts[2].strip()
                if value:
                    result[key] = value
        return result

    @property
    def serial_number(self):
        return self.data_as_dict.get('SN', None)

    @property
    def timestamp(self):
        raw = self.data_as_dict.get('T', None)
        if isinstance(raw, six.string_types) and len(raw) == 12:
            soft_assert_type_text(raw)
            return "20%s-%s-%s %s:%s:%s" % (
                raw[4:6],
                raw[2:4],
                raw[0:2],
                raw[6:8],
                raw[8:10],
                raw[10:12],
            )
        else:
            return None

    @classmethod
    def get_all_ids(cls):
        result = cls.view('wisepill/device_event', include_docs=False)
        return [row['id'] for row in result]
