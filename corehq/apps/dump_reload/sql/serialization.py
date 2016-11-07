from __future__ import absolute_import, unicode_literals

import json

import datetime
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
        self.stream.write("\n")

    def end_object(self, obj):
        # self._current has the field data
        self.stream.write("\n")
        json.dump(self.get_dump_object(obj), self.stream,
                  cls=CommCareJSONEncoder, **self.json_kwargs)
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
