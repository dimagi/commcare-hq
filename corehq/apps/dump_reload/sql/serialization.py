from __future__ import absolute_import, unicode_literals

import json
import six

import datetime
from copy import copy

from django.core.serializers.json import (
    Serializer as JsonSerializer,
    DjangoJSONEncoder)

from dimagi.utils.parsing import json_format_datetime


class JsonLinesSerializer(JsonSerializer):
    """
    Convert a queryset to JSON outputting one object per line
    """
    def start_serialization(self):
        self._init_options()

    def end_serialization(self):
        pass

    def end_object(self, obj):
        # self._current has the field data
        json_kwargs = copy(self.json_kwargs)
        json_kwargs['cls'] = CommCareJSONEncoder
        json_dump = json.dumps(self.get_dump_object(obj), **json_kwargs)
        if six.PY3:
            json_dump = json_dump.encode('utf-8')
        self.stream.write(json_dump)
        self.stream.write(b"\n")
        self._current = None


class CommCareJSONEncoder(DjangoJSONEncoder):
    """
    Custom version of the DjangoJSONEncoder that formats datetime's with all 6 microsecond digits
    """
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return json_format_datetime(o)
        else:
            return super(CommCareJSONEncoder, self).default(o)
