from __future__ import absolute_import, unicode_literals

import json
from copy import copy

import six
from django.core.serializers.json import (
    Serializer as JsonSerializer)

from corehq.util.json import CommCareJSONEncoder


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
