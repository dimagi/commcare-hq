import json
from copy import copy

from django.core.serializers.json import Serializer as JsonSerializer

from corehq.motech.const import PASSWORD_PLACEHOLDER
from corehq.util.json import CommCareJSONEncoder


class JsonLinesSerializer(JsonSerializer):
    """
    Convert a queryset to JSON outputting one object per line
    """

    def serialize(
        self,
        queryset,
        *,
        stream=None,
        fields=None,
        use_natural_foreign_keys=False,
        use_natural_primary_keys=False,
        progress_output=None,
        object_count=0,
        reset_encrypted_fields=True,
        **options
    ):
        self.reset_encrypted_fields = reset_encrypted_fields
        super().serialize(
            queryset,
            stream=stream,
            fields=fields,
            use_natural_foreign_keys=use_natural_foreign_keys,
            use_natural_primary_keys=use_natural_primary_keys,
            progress_output=progress_output,
            object_count=object_count,
            **options
        )

    def start_serialization(self):
        self._init_options()

    def end_serialization(self):
        pass

    def get_dump_object(self, obj):
        dumped_obj = super().get_dump_object(obj)
        if self.reset_encrypted_fields and hasattr(obj, 'encrypted_fields'):
            for field in obj.encrypted_fields():
                dumped_obj['fields'][field] = PASSWORD_PLACEHOLDER
        return dumped_obj

    def end_object(self, obj):
        # self._current has the field data
        json_kwargs = copy(self.json_kwargs)
        json_kwargs['cls'] = CommCareJSONEncoder
        json_dump = json.dumps(self.get_dump_object(obj), **json_kwargs)
        self.stream.write(json_dump)
        self.stream.write("\n")
        self._current = None
