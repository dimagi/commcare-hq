import io

from memoized import memoized

from couchexport.export import export_raw

from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.icds.location_reassignment.const import (
    EXTRACT_OPERATION,
    MERGE_OPERATION,
    MOVE_OPERATION,
    SPLIT_OPERATION,
)


class Dumper(object):
    def __init__(self, domain):
        """
        Dump all transitions in an excel sheet in a format easy to understand by users
        One tab per location type, with changes specific to the location type
        ToDo: add TestDumper
        See TestDumper.test_dump for example
        """
        self.domain = domain
        self.new_site_codes = []
        self.case_accessor = CaseAccessors(domain)

    def dump(self, transitions_per_location_type):
        """
        :param transitions_per_location_type: location types mapped to transitions where
        each transition is a dict with an operation
        like merge or split mapped to details for the operation
        Check Parser for the expected format for each operation
        """
        location_types = list(transitions_per_location_type.keys())
        headers = [[location_type, ['from', 'transition', 'to', 'Missing', 'Archived', 'Cases']]
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
        self.old_site_codes = self._get_old_site_codes(transitions)

    @staticmethod
    def _get_destination_site_codes(transitions):
        # find all sites codes of the destination/final locations
        new_site_codes = []
        for transition in transitions:
            for operation, details in transition.items():
                # in case of split final site codes is a list itself and is the value in the dict
                if operation == SPLIT_OPERATION:
                    [new_site_codes.extend(to_site_codes) for to_site_codes in list(details.values())]
                else:
                    new_site_codes.extend(list(details.keys()))
        return new_site_codes

    @staticmethod
    def _get_old_site_codes(transitions):
        # find all sites codes of the destination/final locations
        old_site_codes = []
        for transition in transitions:
            for operation, details in transition.items():
                # in case of merge old site code is the key in the dict
                if operation == SPLIT_OPERATION:
                    old_site_codes.extend(list(details.keys()))
                # in case of merge old site codes is a list itself and is the value in the dict
                elif operation == MERGE_OPERATION:
                    [old_site_codes.extend(from_site_codes) for from_site_codes in list(details.values())]
                else:
                    old_site_codes.extend(list(details.values()))
        return old_site_codes

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
                destination in self.archived_sites_codes,
                self._get_count_of_cases_owned(source)]

    def _get_rows_for_split(self, details):
        return [
            self._build_row(source, SPLIT_OPERATION, destination)
            for source, destinations in details.items()
            for destination in destinations
        ]

    @memoized
    def _get_count_of_cases_owned(self, site_code):
        location_id = self._old_location_ids_by_site_code()[site_code]
        return len(self.case_accessor.get_case_ids_by_owners([location_id]))

    @memoized
    def _old_location_ids_by_site_code(self):
        return {
            loc.site_code: loc.location_id
            for loc in
            SQLLocation.active_objects.filter(domain=self.domain, site_code__in=self.old_site_codes)
        }
