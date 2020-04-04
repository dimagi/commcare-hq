import io

from couchexport.export import export_raw

from corehq.apps.locations.models import SQLLocation
from custom.icds.location_reassignment.const import (
    EXTRACT_OPERATION,
    MERGE_OPERATION,
    MOVE_OPERATION,
    SPLIT_OPERATION,
)


class Dumper(object):
    def __init__(self):
        """
        Dump all transitions in an excel sheet in a format easy to understand by users
        One tab per location type, with changes specific to the location type
        ToDo: add TestDumper
        See TestDumper.test_dump for example
        """
        self.new_site_codes = []

    def dump(self, transitions_per_location_type):
        """
        :param transitions_per_location_type: location types mapped to transitions where
        each transition is a dict with an operation
        like merge or split mapped to details for the operation
        Check Parser for the expected format for each operation
        """
        location_types = list(transitions_per_location_type.keys())
        headers = [[location_type, ['from', 'transition', 'to', 'Missing', 'Archived']]
                   for location_type in location_types]
        stream = io.BytesIO()
        self._setup_site_codes(list(transitions_per_location_type.values()))
        rows = [(k, v) for k, v in self._rows(transitions_per_location_type).items()]
        export_raw(headers, rows, stream)
        stream.seek(0)
        return stream

    def _setup_site_codes(self, transitions):
        # from the site codes of the destination locations find sites codes that are
        # not present in the system yet and
        # that are present but archived
        destination_site_codes = self._get_destination_site_codes(transitions)
        site_codes_present = (
            SQLLocation.active_objects.filter(site_code__in=destination_site_codes).
            values_list('site_code', flat=True)
        )
        self.new_site_codes = set(destination_site_codes) - set(site_codes_present)
        self.archived_sites_codes = set(
            SQLLocation.inactive_objects.filter(site_code__in=destination_site_codes).
            values_list('site_code', flat=True)
        )

    @staticmethod
    def _get_destination_site_codes(transitions):
        # find all sites codes of the destination/final locations
        new_site_codes = []
        for transition in transitions:
            for operation, details in transition.items():
                if operation == SPLIT_OPERATION:
                    [new_site_codes.extend(to_site_codes) for to_site_codes in list(details.values())]
                else:
                    new_site_codes.extend(list(details.keys()))
        return new_site_codes

    def _rows(self, transitions_per_location_type):
        rows = {location_type: [] for location_type in transitions_per_location_type}
        for location_type, transitions in transitions_per_location_type.items():
            for operation, details in transitions.items():
                rows[location_type].extend(self._get_rows_for_operation(operation, details))
        return rows

    def _get_rows_for_operation(self, operation, details):
        rows = []
        if operation == MERGE_OPERATION:
            rows.extend(self._get_rows_for_merge(details))
        elif operation == SPLIT_OPERATION:
            rows.extend(self._get_rows_for_split(details))
        elif operation in [MOVE_OPERATION, EXTRACT_OPERATION]:
            for destination, source in details.items():
                rows.append(self._build_row(source, operation, destination))
        return rows

    def _get_rows_for_merge(self, details):
        return [
            self._build_row(source, MERGE_OPERATION, destination)
            for destination, sources in details.items()
            for source in sources
        ]

    def _build_row(self, source, operation, destination):
        return [source, operation, destination,
                destination in self.new_site_codes,
                destination in self.archived_sites_codes]

    def _get_rows_for_split(self, details):
        return [
            self._build_row(source, SPLIT_OPERATION, destination)
            for source, destinations in details.items()
            for destination in destinations
        ]
