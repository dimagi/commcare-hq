#!/usr/bin/env python
"""
Create missing parent index on plw_mother_case cases in the wfp-awerial-1
domain affected by bug HI-161
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from django.core.management import BaseCommand

from casexml.apps.case.mock import CaseBlock
from corehq.apps.hqcase.dbaccessors import get_cases_in_domain
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.util import SYSTEM_USER_ID

DOMAIN = 'wfp-awerial-1'
CASE_TYPE = 'plw_mother_case'
DEVICE_ID = 'HI-161_parent_index'


class Command(BaseCommand):
    help = ('Create missing parent index on plw_mother_case cases in the '
            'wfp-awerial-1 domain affected by bug HI-161.')

    def add_arguments(self, parser):
        parser.add_argument('--domain')
        parser.add_argument('--case-type')
        parser.add_argument('--dry-run', action='store_true')

    def get_mother_case_ids(self):
        """
        Returns a dictionary mapping project-specific "mother IDs" to case IDs.
        """
        # It seems in some versions of the app, case.plw_id is used instead
        # of case.mother_id
        return {
            getattr(case, 'mother_id', case.plw_id): case.get_id
            for case in get_cases_in_domain(self.domain, type=self.case_type)
            if getattr(case, 'mother_id', None) or getattr(case, 'plw_id', None)
        }

    def create_indices(self):
        """
        Submits case blocks to create parent indices on child cases.

        Changes made by this script are tagged using device_id.
        """
        errors = []
        case_blocks = []
        for case in get_cases_in_domain(self.domain, type=self.case_type):
            if getattr(case, 'child_mother_id', None):
                relationships = {index.relationship for index in case.indices}
                if 'child' in relationships:
                    # This case already has a parent
                    continue

                try:
                    parent_id = self.parent_case_ids[case.child_mother_id]
                except KeyError:
                    errors.append(
                        'Parent case ID not found for mother ID "{mother}". '
                        'Skipping child case "{child}".'.format(
                            mother=case.child_mother_id,
                            child=case.get_id)
                    )
                    continue

                case_blocks.append(CaseBlock(
                    case_id=case.get_id,
                    user_id=SYSTEM_USER_ID,
                    index={'child': ('parent', parent_id)}
                ))
        if not self.dry_run:
            submit_case_blocks(
                [cb.as_bytes() for cb in case_blocks],
                self.domain,
                device_id=DEVICE_ID,
            )
        return errors

    def handle(self, **options):
        self.domain = options.get('domain') or DOMAIN
        self.case_type = options.get('case_type') or CASE_TYPE
        self.dry_run = options.get('dry_run', False)

        # There are 2229 plw_mother_case cases in the wfp-awerial-1
        # domain. This script takes a two-pass strategy. In the first
        # pass it stores the case IDs of all mothers. In the second pass
        # it creates parent indices on child cases.
        self.parent_case_ids = self.get_mother_case_ids()
        errors = self.create_indices()

        if errors:
            print('Encountered errors:')
            print('\n'.join(errors))
