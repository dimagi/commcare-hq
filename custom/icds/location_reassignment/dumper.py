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
    PERSON_CASE_TYPE,
    SPLIT_OPERATION,
)
from custom.icds.location_reassignment.utils import (
    get_household_case_ids,
    get_household_child_cases_by_owner,
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
            SQLLocation.objects.filter(site_code__in=destination_site_codes, is_archived=True).
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


class HouseHolds(object):
    valid_operations = [SPLIT_OPERATION, EXTRACT_OPERATION]
    headers = ['Name of AWC', 'Name of Household', 'Date of Registration', 'Religion',
               'Caste', 'APL/BPL', 'Number of Household Members', 'Household Members']

    def __init__(self, domain):
        self.domain = domain

    def dump(self, transitions):
        """
        :return: excel workbook with one tab with title as old location's site code,
        which holds details all household cases assigned to it
        """
        rows = {}
        for operation, details in transitions.items():
            if operation in self.valid_operations:
                rows.update(self._get_rows_for_location(operation, details))
        if rows:
            stream = io.BytesIO()
            rows = [(k, v) for k, v in rows.items()]
            headers = [[site_code, self.headers] for site_code in rows]
            export_raw(headers, rows, stream)
            stream.seek(0)
            return stream

    def _get_rows_for_location(self, operation, details):
        rows = {}
        if operation == SPLIT_OPERATION:
            for site_code in details.keys():
                rows[site_code] = self._build_rows(site_code)
        elif operation == EXTRACT_OPERATION:
            for site_code in details.values():
                rows[site_code] = self._build_rows(site_code)
        return rows

    def _build_rows(self, site_code):
        rows = []
        location = SQLLocation.active_objects.get(domain=self.domain, site_code=site_code)
        case_ids = get_household_case_ids(self.domain, location.location_id)
        for case_id in case_ids:
            household_case = CaseAccessors(self.domain).get_case(case_id)
            person_cases = get_household_child_cases_by_owner(
                self.domain, case_id, location.location_id, [PERSON_CASE_TYPE])
            rows.append([
                location.name,
                household_case.name,
                household_case.get_case_property('hh_reg_date'),
                household_case.get_case_property('hh_religion'),
                household_case.get_case_property('hh_caste'),
                household_case.get_case_property('hh_bpl_apl'),
                len(person_cases),
                ",".join([
                    "%s (%s/%s)" % (
                        case.name, case.get_case_property('age_at_reg'), case.get_case_property('sex'))
                    for case in person_cases
                ])
            ])
        return rows
