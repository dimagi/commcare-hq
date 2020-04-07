import io
import itertools
from collections import defaultdict
from copy import deepcopy

from memoized import memoized
from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation

from corehq.apps.es import UserES
from corehq.apps.locations.models import SQLLocation
from custom.icds.location_reassignment.const import (
    CURRENT_LGD_CODE,
    CURRENT_NAME,
    CURRENT_PARENT_NAME,
    CURRENT_PARENT_SITE_CODE,
    CURRENT_PARENT_TYPE,
    CURRENT_SITE_CODE_COLUMN,
    NEW_LGD_CODE,
    NEW_NAME,
    NEW_PARENT_SITE_CODE,
    NEW_SITE_CODE_COLUMN,
    NEW_USERNAME_COLUMN,
    OPERATION_COLUMN,
    USERNAME_COLUMN,
    VALID_OPERATIONS,
)


class Download(object):
    def __init__(self, domain, location_id):
        """
        Generates an Excel file stream
        With details of all locations related to a location
        and users assigned to these locations.
        Each sheet corresponds to a location type.
        """
        self.location = SQLLocation.active_objects.get(location_id=location_id, domain=domain)

    def dump(self):
        self._init_location_details()
        self._populate_assigned_users()
        wb = self._create_workbook()
        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        return stream

    def _init_location_details(self):
        # setup details for the main location and all related locations
        self._location_details_by_location_id = {}
        for location in self._locations():
            self._location_details_by_location_id[location.location_id] = {
                'name': location.name,
                'type_name': location.location_type.name,
                'site_code': location.site_code,
                'lgd_code': location.metadata.get('lgd_code', ''),
                'parent_location_id': location.parent_location_id,
                'location_type': location.location_type.code,
                'assigned_users': [],
            }

    def _locations(self):
        # fetch all locations necessary for this download request
        ancestors = list(self.location.get_ancestors().select_related('location_type'))
        self_and_descendants = list(self.location.get_descendants(include_self=True)
                                    .filter(is_archived=False).select_related('location_type'))
        return ancestors + self_and_descendants

    def _populate_assigned_users(self):
        # allot assign user details to each location
        for username, assigned_location_ids in self._get_assigned_location_ids().items():
            for location_id in assigned_location_ids:
                if location_id in self._location_details_by_location_id:
                    self._location_details_by_location_id[location_id]['assigned_users'].append(username)

    def _get_assigned_location_ids(self):
        location_ids = list(self._location_details_by_location_id.keys())
        assigned_location_ids_per_username = {}
        user_details = UserES().location(location_ids).values_list('base_username', 'assigned_location_ids')
        for username, assigned_location_ids in user_details:
            if not isinstance(assigned_location_ids, list):
                assigned_location_ids = [assigned_location_ids]
            assigned_location_ids_per_username[username] = assigned_location_ids
        return assigned_location_ids_per_username

    def _create_workbook(self):
        wb = Workbook()
        # workbook adds an empty sheet for new workbook unless it is write only
        wb.remove(wb.active)
        for location_type, rows in self._create_rows().items():
            worksheet = wb.create_sheet(location_type)
            uniq_headers = self._extract_unique_headers(rows)
            worksheet.append(uniq_headers)
            for row in rows:
                worksheet.append([row.get(header) for header in uniq_headers])
            self._add_validation(worksheet)
        return wb

    @staticmethod
    def _add_validation(worksheet):
        operation_data_validation = DataValidation(type="list", formula1='"%s"' % (','.join(VALID_OPERATIONS)))
        worksheet.add_data_validation(operation_data_validation)
        for header_cell in worksheet[1]:
            if header_cell.value == OPERATION_COLUMN:
                letter = header_cell.column_letter
                operation_data_validation.add(f"{letter}2:{letter}{worksheet.max_row}")

    def _create_rows(self):
        def append_row(username):
            row = deepcopy(location_content)
            row[USERNAME_COLUMN] = username
            row[NEW_USERNAME_COLUMN] = ''
            row[OPERATION_COLUMN] = ''
            rows[location_type].append(row)

        # location type code mapped to rows which is a list of dictionaries to pull headers later using keys
        rows = defaultdict(list)
        for location_id, location_details in self._location_details_by_location_id.items():
            location_content = self._location_content(location_id)
            location_type = location_details['location_type']
            if location_details['assigned_users']:
                for username in location_details['assigned_users']:
                    append_row(username)
            else:
                # set up one row for location that has no user assigned
                append_row('')
        return rows

    @memoized
    def _location_content(self, location_id):
        # memoized static content for each location
        location_details = self._location_details_by_location_id[location_id]
        location_parent_id = location_details['parent_location_id']
        location_content = {
            CURRENT_NAME: location_details['name'],
            NEW_NAME: '',
            CURRENT_SITE_CODE_COLUMN: location_details['site_code'],
            NEW_SITE_CODE_COLUMN: '',
            CURRENT_LGD_CODE: location_details['lgd_code'],
            NEW_LGD_CODE: '',
        }
        if location_parent_id and location_parent_id in self._location_details_by_location_id:
            location_parent_details = self._location_details_by_location_id[location_parent_id]
            location_content.update({
                CURRENT_PARENT_TYPE: location_parent_details['type_name'],
                CURRENT_PARENT_NAME: location_parent_details['name'],
                CURRENT_PARENT_SITE_CODE: location_parent_details['site_code'],
                NEW_PARENT_SITE_CODE: ''
            })
        return location_content

    @staticmethod
    def _extract_unique_headers(rows):
        # extract headers preserving the order of occurrence
        headers_for_all_rows = list(itertools.chain.from_iterable(rows))
        uniq_headers = []
        for h in headers_for_all_rows:
            if h not in uniq_headers:
                uniq_headers.append(h)
        return uniq_headers
