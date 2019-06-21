from __future__ import absolute_import
from __future__ import unicode_literals

import datetime

from django.core.serializers.json import DjangoJSONEncoder
from django.utils.functional import Promise
from dimagi.utils.parsing import json_format_datetime


class CommCareJSONEncoder(DjangoJSONEncoder):
    """
    Custom version of the DjangoJSONEncoder that formats datetime's with all 6 microsecond digits
    """
    def default(self, o):
        if isinstance(o, Promise):
            return o._proxy____cast()
        elif isinstance(o, datetime.datetime):
            return json_format_datetime(o)
        else:
            return super(CommCareJSONEncoder, self).default(o)
