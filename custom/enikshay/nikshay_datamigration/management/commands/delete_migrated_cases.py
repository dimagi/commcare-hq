from __future__ import absolute_import
from __future__ import print_function
from itertools import chain

from django.core.management import BaseCommand

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.case_utils import (
    CASE_TYPE_DRTB_HIV_REFERRAL,
    CASE_TYPE_EPISODE,
    CASE_TYPE_OCCURRENCE,
    CASE_TYPE_PERSON,
    get_first_parent_of_case,
)
from six.moves import input


def _get_children_cases_by_type(domain, parent_case_id, child_case_type):
    case_accessor = CaseAccessors(domain)
    return [
        child_case for child_case in case_accessor.get_reverse_indexed_cases([parent_case_id])
        if child_case.type == child_case_type
    ]


def _concatenate_list_of_lists(list_of_lists):
    return list(chain(*list_of_lists))


def _get_case_ids_related_to_person(domain, person_case_id):
    case_accessor = CaseAccessors(domain)

    person_case = case_accessor.get_case(person_case_id)
    assert person_case.type == 'person'
    assert person_case.dynamic_case_properties().get('migration_created_case') == 'true'

    all_occurrence_cases = _get_children_cases_by_type(domain, person_case.case_id, CASE_TYPE_OCCURRENCE)
    for occurrence_case in all_occurrence_cases:
        assert occurrence_case.dynamic_case_properties().get('migration_created_case') == 'true'

    all_episode_cases = _concatenate_list_of_lists([
        _get_children_cases_by_type(domain, occurrence_child_case.case_id, CASE_TYPE_EPISODE)
        for occurrence_child_case in all_occurrence_cases
    ])
    for episode_case in all_episode_cases:
        assert episode_case.dynamic_case_properties().get('migration_created_case') == 'true'

    all_drtb_hiv_referral_cases = _concatenate_list_of_lists([
        _get_children_cases_by_type(domain, episode_child_case.case_id, CASE_TYPE_DRTB_HIV_REFERRAL)
        for episode_child_case in all_episode_cases
    ])
    for drtb_hiv_referral_case in all_drtb_hiv_referral_cases:
        assert drtb_hiv_referral_case.dynamic_case_properties().get('migration_created_case') == 'true'

    return _concatenate_list_of_lists([
        [person_case.case_id],
        [occurrence_child_case.case_id for occurrence_child_case in all_occurrence_cases],
        [episode_child_case.case_id for episode_child_case in all_episode_cases],
        [drtb_hiv_referral_case.case_id for drtb_hiv_referral_case in all_drtb_hiv_referral_cases],
    ])


def _get_case_ids_related_to_episode(domain, episode_case_id):
    occurrence_case = get_first_parent_of_case(domain, episode_case_id, CASE_TYPE_OCCURRENCE)
    person_case = get_first_parent_of_case(domain, occurrence_case.case_id, CASE_TYPE_PERSON)
    return _get_case_ids_related_to_person(domain, person_case.case_id)


_case_type_to_related_cases_func = {
    'episode': _get_case_ids_related_to_episode,
    'person': _get_case_ids_related_to_person,
}


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            'case_type',
            choices=list(_case_type_to_related_cases_func),
        )
        parser.add_argument(
            'case_ids',
            metavar='case_id',
            nargs='+',
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            default=False,
            help='For unit tests only. Skips user confirmation.'
        )

    def handle(self, domain, case_type, case_ids, **options):
        if not options.get('noinput'):
            confirm = input(
                u"""
                Are you sure you want to delete all these cases, and their associated
                person, occurrence, episode, and drtb-hiv-referral cases?

                Type DELETE and press Enter to confirm.
                """
            )
            if confirm != "DELETE":
                print("\n\t\tCancelled.")
                return
            else:
                print("\n\t\tDeleting...")

        get_related_cases_func = _case_type_to_related_cases_func[case_type]

        migrated_case_ids = _concatenate_list_of_lists([
            get_related_cases_func(domain, case_id) for case_id in case_ids
        ])
        CaseAccessors(domain).soft_delete_cases(migrated_case_ids)
