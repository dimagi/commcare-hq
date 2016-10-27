from __future__ import absolute_import, unicode_literals

import json

from django.core.serializers.json import (
    Serializer as JsonSerializer,
    DjangoJSONEncoder)


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
                  cls=DjangoJSONEncoder, **self.json_kwargs)
        self._current = None
