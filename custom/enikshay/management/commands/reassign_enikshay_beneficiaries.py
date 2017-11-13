from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import csv
import datetime
from django.core.management.base import BaseCommand

from dimagi.utils.chunked import chunked
from dimagi.utils.decorators.memoized import memoized

from casexml.apps.case.mock import CaseBlock
from corehq.apps.es import CaseSearchES
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.log import with_progress_bar

from custom.enikshay.const import ENROLLED_IN_PRIVATE
from custom.enikshay.case_utils import CASE_TYPE_PERSON


class Command(BaseCommand):

    log_columns = [
        'case_id',
        'old facility_assigned_to',
        'old facility is pcp or pac',
        'old owner_id',
        'old owner is pcp or pac',
        'registered_by',
        'registered_by is pcp',
        'new facility_assigned_to',  # if changed
        'new owner_id',  # if changed
        'modified',
    ]

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--commit', action='store_true')

    def handle(self, domain, **options):
        self.domain = domain
        case_blocks = []
        filename = 'beneficiary_assignment-{}.csv'.format(
            datetime.datetime.now().strftime('%Y-%m-%d_%H.%M.%S'))
        with open(filename, 'w') as f:
            writer = csv.DictWriter(f, self.log_columns)
            writer.writeheader()
            person_ids = self.get_person_ids()
            for person in with_progress_bar(self.get_person_cases(person_ids), len(person_ids)):
                data = self.get_person_data(person)
                writer.writerow(data)
                if data['modified']:
                    case_blocks.append(self.get_case_block(data))
        if options['commit']:
            print("Saving cases")
            self.save_case_blocks(case_blocks)

    def get_person_data(self, person):
        facility_id = person.get_case_property('facility_assigned_to')
        registered_by = person.get_case_property('registered_by')
        data = {
            'case_id': person.case_id,
            'old facility_assigned_to': facility_id,
            'old facility is pcp or pac': (facility_id in self.pcp_locations
                                           or facility_id in self.pac_locations),
            'old owner_id': person.owner_id,
            'old owner is pcp or pac': (person.owner_id in self.pcp_locations
                                        or person.owner_id in self.pac_locations),
            'registered_by': registered_by,
            'registered_by is pcp': registered_by in self.pcp_locations,
            'modified': False,
        }

        if data['registered_by is pcp']:
            if not data['old facility is pcp or pac']:
                data['new facility_assigned_to'] = registered_by
                data['modified'] = True
            if not data['old owner is pcp or pac'] and data['old owner_id'] != '_archive_':
                data['new owner_id'] = registered_by
                data['modified'] = True

        return data

    def get_case_block(self, data):
        return CaseBlock(
            case_id=data['case_id'],
            owner_id=data.get('new owner_id', CaseBlock.undefined),
            update=(
                {'facility_assigned_to': data['new owner_id']}
                if 'new owner_id' in data else None
            ),
        )

    def save_case_blocks(self, case_blocks):
        for chunk in chunked(case_blocks, 100):
            submit_case_blocks(
                [case_block.as_string() for case_block in chunk],
                self.domain,
                device_id="reassign_enikshay_beneficiaries",
            )

    @property
    @memoized
    def pcp_locations(self):
        return set(SQLLocation.active_objects
                   .filter(domain=self.domain,
                           location_type__code__exact='pcp')
                   .location_ids())

    @property
    @memoized
    def pac_locations(self):
        return set(SQLLocation.active_objects
                   .filter(domain=self.domain,
                           location_type__code__exact='pac')
                   .location_ids())

    def get_person_cases(self, person_ids):
        return CaseAccessors(self.domain).iter_cases(person_ids)

    def get_person_ids(self):
        return (CaseSearchES()
                .domain(self.domain)
                .case_type(CASE_TYPE_PERSON)
                .case_property_query(ENROLLED_IN_PRIVATE, 'true')
                .get_ids())
