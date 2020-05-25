import io

from memoized import memoized

from couchexport.export import export_raw

from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.icds.location_reassignment.const import (
    DUMPER_COLUMNS,
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
        headers = [[location_type, DUMPER_COLUMNS]
                   for location_type in location_types]
        stream = io.BytesIO()
        all_transitions = []
        for transitions in transitions_per_location_type.values():
            all_transitions.extend(transitions)
        self._setup_site_codes(all_transitions)
        rows = self._rows(transitions_per_location_type).items()
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
            SQLLocation.objects.filter(site_code__in=destination_site_codes, is_archived=True).
            values_list('site_code', flat=True)
        )
        self.old_site_codes = self._get_old_site_codes(transitions)

    @staticmethod
    def _get_destination_site_codes(transitions):
        # find all sites codes of the destination/final locations
        new_site_codes = []
        for transition in transitions:
            new_site_codes.extend(transition.new_site_codes)
        return new_site_codes

    @staticmethod
    def _get_old_site_codes(transitions):
        # find all sites codes of the old locations
        old_site_codes = []
        for transition in transitions:
            old_site_codes.extend(transition.old_site_codes)
        return old_site_codes

    def _rows(self, transitions_per_location_type):
        rows = {location_type: [] for location_type in transitions_per_location_type}
        for location_type, transitions in transitions_per_location_type.items():
            for transition in transitions:
                rows[location_type].extend(self._get_rows_for_operation(transition))
        return rows

    def _get_rows_for_operation(self, transition):
        operation = transition.operation
        rows = []
        if operation == MERGE_OPERATION:
            rows.extend(self._get_rows_for_merge(transition))
        elif operation == SPLIT_OPERATION:
            rows.extend(self._get_rows_for_split(transition))
        elif operation in [MOVE_OPERATION, EXTRACT_OPERATION]:
            source = transition.old_site_codes[0]
            destination = transition.new_site_codes[0]
            rows.append(self._build_row(source, operation, destination))
        return rows

    def _get_rows_for_merge(self, transition):
        sources = transition.old_site_codes
        destination = transition.new_site_codes[0]
        return [
            self._build_row(source, MERGE_OPERATION, destination)
            for source in sources
        ]

    def _build_row(self, source, operation, destination):
        return [source, operation, destination,
                destination in self.new_site_codes,
                destination in self.archived_sites_codes,
                self._get_count_of_cases_owned(source)]

    def _get_rows_for_split(self, transition):
        source = transition.old_site_codes[0]
        destinations = transition.new_site_codes
        return [
            self._build_row(source, SPLIT_OPERATION, destination)
            for destination in destinations
        ]

    @memoized
    def _get_count_of_cases_owned(self, site_code):
        location_id = self._old_location_ids_by_site_code().get(site_code)
        if location_id:
            return len(self.case_accessor.get_case_ids_by_owners([location_id]))
        return "Not Found"

    @memoized
    def _old_location_ids_by_site_code(self):
        return {
            loc.site_code: loc.location_id
            for loc in
            SQLLocation.active_objects.filter(domain=self.domain, site_code__in=self.old_site_codes)
        }
