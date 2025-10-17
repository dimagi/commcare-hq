import uuid
import datetime

from copy import copy
from django.core.management import BaseCommand

from corehq.apps.es import CaseSearchES
from corehq.form_processor.models import CommCareCase
from corehq.util.log import with_progress_bar

from casexml.apps.case.mock import CaseIndex, CaseStructure, CaseFactory

DOMAIN = "ucr-example"
MULTIPLIER = 200
HOUSEHOLD_CASE_TYPE = "household"
CLIENT_CASE_TYPE = "client"


class Command(BaseCommand):
    help = "Create duplicate cases for UCR PoC"

    def add_arguments(self, parser):
        parser.add_argument(
            '--real-run',
            action='store_true',
            default=False,
            help='Actually modify the database, otherwise just log what will happen',
        )

    def handle(self, *args, **options):
        """
        We iterate over household case IDs
        - then duplicate it and all its child cases
        - update certain case properties & setup new indices
        - save the cases (one form at a time)
        - we repeat this X times for each household, X is the multiplier set
        """
        # get household case ids to duplicate
        is_real_run = options['real_run']

        household_case_ids = (
            CaseSearchES().domain(DOMAIN).case_type(HOUSEHOLD_CASE_TYPE).
            server_modified_range(lt=datetime.date(2025, 10, 15)).
            values_list('_id', flat=True)
        )

        next_household_id = len(CommCareCase.objects.get_case_ids_in_domain(DOMAIN, HOUSEHOLD_CASE_TYPE)) + 1
        next_client_id = len(CommCareCase.objects.get_case_ids_in_domain(DOMAIN, CLIENT_CASE_TYPE)) + 1

        for case_id in with_progress_bar(household_case_ids):
            to_save = []
            household_case = CommCareCase.objects.get_case(case_id, DOMAIN)
            for duplicate_attempt in range(0, MULTIPLIER):
                new_case_structures, next_household_id, next_client_id = _duplicate_household_and_all_child_cases(
                    household_case=household_case,
                    next_household_id=next_household_id,
                    next_client_id=next_client_id,
                )
                to_save.extend(new_case_structures)
            if is_real_run:
                _save_cases(to_save)
            else:
                pass
                # print([b.as_text() for b in CaseFactory(domain=DOMAIN).get_case_blocks(to_save)])


def _duplicate_household_and_all_child_cases(household_case, next_household_id, next_client_id):
    new_case_structures = []
    household_case_case_structure = _duplicate_household_case(household_case, next_household_id)
    new_case_structures.append(household_case_case_structure)
    next_household_id += 1

    client_cases = household_case.get_subcases()
    for client_case in client_cases:
        client_case_case_structure = _duplicate_client_case(client_case, household_case_case_structure, next_client_id)
        new_case_structures.append(client_case_case_structure)
        next_client_id += 1

        for client_child_case in client_case.get_subcases():
            client_child_case_case_structure = _duplicate_client_child_case(client_child_case,
                                                                            client_case_case_structure)
            new_case_structures.append(client_child_case_case_structure)

            for client_child_child_case in client_child_case.get_subcases():
                client_child_child_case_case_structure = _duplicate_client_child_child_case(
                    client_child_child_case, client_child_case_case_structure
                )
                new_case_structures.append(client_child_child_case_case_structure)

    return new_case_structures, next_household_id, next_client_id


def _duplicate_household_case(household_case, next_household_id):
    case_properties = copy(household_case.case_json)
    case_properties['household_id'] = _format_household_id_for_case(next_household_id)
    return CaseStructure(
        case_id=uuid.uuid4().hex,
        attrs={
            'create': True,
            'case_type': HOUSEHOLD_CASE_TYPE,
            'case_name': _format_household_id_for_case(next_household_id),
            'owner_id': household_case.owner_id,
            'update': case_properties,
        }
    )



def _format_household_id_for_case(next_household_id):
    # return in format H[8 digit number]
    # like H00010000 for 10000
    return "H" + '0'*(8 - len(str(next_household_id))) + str(next_household_id)


def _duplicate_client_case(client_case, new_household_case_case_structure, next_client_id):
    case_properties = copy(client_case.case_json)
    case_properties['household_id'] = new_household_case_case_structure.attrs['case_name']
    case_properties['parent_type'] = new_household_case_case_structure.attrs['case_type']
    case_properties['parent_id'] = new_household_case_case_structure.case_id
    return CaseStructure(
        case_id=uuid.uuid4().hex,
        attrs={
            'create': True,
            'case_type': CLIENT_CASE_TYPE,
            'case_name': _format_client_id_for_case(next_client_id),
            'owner_id': client_case.owner_id,
            'update': case_properties
        },
        indices=[
            CaseIndex(
                new_household_case_case_structure,
            )
        ],
        walk_related=False,
    )


def _format_client_id_for_case(next_client_id):
    # return in format CL[8 digit number]
    # like CL00003000 for 3000
    return "CL" + '0'*(8 - len(str(next_client_id))) + str(next_client_id)


def _duplicate_client_child_case(client_child_case, client_case_case_structure):
    case_properties = copy(client_child_case.case_json)
    client_id = client_case_case_structure.attrs['case_name']
    case_properties['household_id'] = client_case_case_structure.attrs['update']['household_id']
    case_properties['client_id'] = client_id
    case_properties['client_name'] = client_id

    case_properties['parent_type'] = client_case_case_structure.attrs['case_type']
    case_properties['parent_id'] = client_case_case_structure.case_id

    return CaseStructure(
        case_id=uuid.uuid4().hex,
        attrs={
            'create': True,
            'case_type': client_child_case.type,
            'case_name': client_id, # Yes, this is same as the client's
            'owner_id': client_child_case.owner_id,
            'update': case_properties,
        },
        indices=[
            CaseIndex(
                client_case_case_structure,
            )
        ],
        walk_related=False,
    )

def _duplicate_client_child_child_case(client_child_child_case, client_child_case_case_structure):
    case_properties = copy(client_child_child_case.case_json)
    client_id = client_child_case_case_structure.attrs['case_name']
    case_properties['household_id'] = client_child_case_case_structure.attrs['update']['household_id']
    case_properties['client_id'] = client_id
    case_properties['client_name'] = client_id
    case_properties['parent_type'] = client_child_case_case_structure.attrs['case_type']
    case_properties['parent_id'] = client_child_case_case_structure.case_id
    return CaseStructure(
        case_id=uuid.uuid4().hex,
        attrs={
            'create': True,
            'case_type': client_child_child_case.type,
            'case_name': client_id,  # Yes, this is same as the client's
            'owner_id': client_child_child_case.owner_id,
            'update': case_properties,
        },
        indices=[
            CaseIndex(
                client_child_case_case_structure,
            )
        ],
        walk_related=False,
    )

def _save_cases(new_case_structures):
    return CaseFactory(domain=DOMAIN).create_or_update_cases(
        case_structures=new_case_structures,
        device_id=__name__
    )
