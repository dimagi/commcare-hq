import json
from copy import copy

from django.core.serializers.json import Serializer as JsonSerializer

from corehq.util.json import CommCareJSONEncoder


class JsonLinesSerializer(JsonSerializer):
    """
    Convert a queryset to JSON outputting one object per line
    """

    def start_serialization(self):
        self._init_options()

    def end_serialization(self):
        pass

    def get_dump_object(self, obj):
        dumped_obj = super().get_dump_object(obj)
        if hasattr(obj, 'encrypted_fields'):
            dumped_obj['fields'].update(obj.encrypted_fields)
        return dumped_obj

    def end_object(self, obj):
        # self._current has the field data
        json_kwargs = copy(self.json_kwargs)
        json_kwargs['cls'] = CommCareJSONEncoder
        json_dump = json.dumps(self.get_dump_object(obj), **json_kwargs)
        self.stream.write(json_dump)
        self.stream.write("\n")
        self._current = None
