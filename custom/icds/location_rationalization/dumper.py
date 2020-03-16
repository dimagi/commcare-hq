import io
from collections import OrderedDict

from couchexport.export import export_raw

from custom.icds.location_rationalization.const import (
    EXTRACT_TRANSITION,
    MERGE_TRANSITION,
    MOVE_TRANSITION,
    SPLIT_TRANSITION,
)


class Dumper(object):
    def __init__(self, location_types):
        self.location_types = location_types

    def dump(self, transitions):
        headers = [[location_type, ['from', 'transition', 'to']] for location_type in self.location_types]
        stream = io.BytesIO()
        rows = [(k, v) for k, v in self._rows(transitions).items()]
        export_raw(headers, rows, stream)
        return stream

    def _rows(self, transitions):
        rows = OrderedDict({location_type: [] for location_type in self.location_types})
        for location_type, operations in transitions.items():
            for operation, details in operations.items():
                rows[location_type].extend(self._get_rows_for_operation(operation, details))
        return rows

    def _get_rows_for_operation(self, operation, details):
        rows = []
        if operation == MERGE_TRANSITION:
            rows.extend(self._get_rows_for_merge(details))
        elif operation == SPLIT_TRANSITION:
            rows.extend(self._get_rows_for_split(details))
        elif operation in [MOVE_TRANSITION, EXTRACT_TRANSITION]:
            for destination, source in details.items():
                rows.append([source, operation, destination])
        return rows

    @staticmethod
    def _get_rows_for_merge(details):
        rows = []
        for destination, sources in details.items():
            for source in sources:
                rows.append([source, MERGE_TRANSITION, destination])
        return rows

    @staticmethod
    def _get_rows_for_split(details):
        rows = []
        for source, destinations in details.items():
            for destination in destinations:
                rows.append([source, SPLIT_TRANSITION, destination])
        return rows
