import json
from copy import copy

from django.core.serializers.json import Serializer as JsonSerializer
from memoized import memoized

from corehq.util.json import CommCareJSONEncoder


@memoized
def _fk_value_is_natural_key(fk_field):
    """Answers the question "Is fk_field's value already the natural_key of the foreign object?"

    For example, case_transaction.case_id is already the natural_key of case_transaction.case.
    Knowing this allows the caller to skip an unnecessary db query to look up the foreign object.
    """
    # e.g. related_model = CommCareCase
    related_model = fk_field.remote_field.model
    # e.g. to_field = 'case_id'
    to_field = fk_field.remote_field.field_name
    if not hasattr(related_model, 'natural_key'):
        return False
    try:
        # natural_key() is an arbitrary instance method, not a field name, so we can only tell
        # whether it returns the to_field value by trying it: set to_field to a challenge value
        # and check natural_key() gives it back. e.g. CommCareCase(case_id=X).natural_key() == X
        challenge = '68bbc985c27d9fd693d72fbeaecd862b90827f64'
        return related_model(**{to_field: challenge}).natural_key() == challenge
    except Exception:
        return False


class JsonLinesSerializer(JsonSerializer):
    """
    Convert a queryset to JSON outputting one object per line
    """

    def start_serialization(self):
        self._init_options()

    def end_serialization(self):
        pass

    def handle_fk_field(self, obj, field):
        """Avoid fetching the foreign object when the FK value is already its natural key.
        e.g. use `case_transaction.case_id` instead of `case_transaction.case.natural_key()`:
        they're identical, and accessing `case_transaction.case` runs an unnecessary db query.
        """
        if self.use_natural_foreign_keys and _fk_value_is_natural_key(field):
            # e.g. self._current['case'] = case_transaction.case_id
            self._current[field.name] = getattr(obj, field.get_attname())
        else:
            super().handle_fk_field(obj, field)

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
