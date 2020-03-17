import io

from couchexport.export import export_raw

from corehq.apps.locations.models import SQLLocation
from custom.icds.location_rationalization.const import (
    EXTRACT_TRANSITION,
    MERGE_TRANSITION,
    MOVE_TRANSITION,
    SPLIT_TRANSITION,
)


class Dumper(object):
    def __init__(self, location_types):
        self.location_types = location_types
        self.new_site_codes = []

    def dump(self, transitions):
        headers = [[location_type, ['from', 'transition', 'to', 'Missing']]
                   for location_type in self.location_types]
        stream = io.BytesIO()
        self._find_missing_site_codes(list(transitions.values()))
        rows = [(k, v) for k, v in self._rows(transitions).items()]
        export_raw(headers, rows, stream)
        return stream

    def _find_missing_site_codes(self, transitions):
        new_site_codes = self._get_all_new_site_codes(transitions)
        site_codes_present = (
            SQLLocation.active_objects.filter(site_code__in=new_site_codes).
            values_list('site_code', flat=True)
        )
        self.new_site_codes = set(new_site_codes) - set(site_codes_present)

    @staticmethod
    def _get_all_new_site_codes(transitions):
        new_site_codes = []
        for transition in transitions:
            for operation, details in transition.items():
                if operation == SPLIT_TRANSITION:
                    [new_site_codes.extend(to_site_codes) for to_site_codes in list(details.values())]
                else:
                    new_site_codes.extend(list(details.keys()))
        return new_site_codes

    def _rows(self, transitions):
        rows = {location_type: [] for location_type in self.location_types}
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
                rows.append([source, operation, destination, destination in self.new_site_codes])
        return rows

    def _get_rows_for_merge(self, details):
        rows = []
        for destination, sources in details.items():
            for source in sources:
                rows.append([source, MERGE_TRANSITION, destination, destination in self.new_site_codes])
        return rows

    def _get_rows_for_split(self, details):
        rows = []
        for source, destinations in details.items():
            for destination in destinations:
                rows.append([source, SPLIT_TRANSITION, destination, destination in self.new_site_codes])
        return rows
