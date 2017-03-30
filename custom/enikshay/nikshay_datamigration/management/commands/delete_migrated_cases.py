from itertools import chain

from django.core.management import BaseCommand

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.case_utils import (
    CASE_TYPE_DRTB_HIV_REFERRAL,
    CASE_TYPE_EPISODE,
    CASE_TYPE_OCCURRENCE,
    CASE_TYPE_PERSON,
)


def _get_parent_case_by_type(domain, child_case_id, parent_case_type):
    case_accessor = CaseAccessors(domain)
    child_case = case_accessor.get_case(child_case_id)
    parent_case_ids = [
        indexed_case.referenced_id for indexed_case in child_case.indices
    ]
    parent_cases = [
        parent_case for parent_case in case_accessor.get_cases(parent_case_ids)
        if parent_case.type == parent_case_type
    ]
    assert len(parent_cases) == 1
    return parent_cases[0]


def _get_children_cases_by_type(domain, parent_case_id, child_case_type):
    case_accessor = CaseAccessors(domain)
    return [
        child_case for child_case in case_accessor.get_reverse_indexed_cases([parent_case_id])
        if child_case.type == child_case_type
    ]


def _concatenate_list_of_lists(list_of_lists):
    return list(chain(*list_of_lists))


def _get_related_case_ids(domain, episode_case_id):
    case_accessor = CaseAccessors(domain)

    episode_case = case_accessor.get_case(episode_case_id)
    assert episode_case.dynamic_case_properties().get('migration_created_case') == 'true'
    occurrence_case = _get_parent_case_by_type(domain, episode_case_id, CASE_TYPE_OCCURRENCE)
    assert occurrence_case.dynamic_case_properties().get('migration_created_case') == 'true'
    person_case = _get_parent_case_by_type(domain, occurrence_case.case_id, CASE_TYPE_PERSON)
    assert person_case.dynamic_case_properties().get('migration_created_case') == 'true'

    all_occurrence_cases = _get_children_cases_by_type(domain, person_case.case_id, CASE_TYPE_OCCURRENCE)
    all_episode_cases = _concatenate_list_of_lists([
        _get_children_cases_by_type(domain, occurrence_child_case.case_id, CASE_TYPE_EPISODE)
        for occurrence_child_case in all_occurrence_cases
    ])
    all_drtb_hiv_referral_cases = _concatenate_list_of_lists([
        _get_children_cases_by_type(domain, episode_child_case.case_id, CASE_TYPE_DRTB_HIV_REFERRAL)
        for episode_child_case in all_episode_cases
    ])

    return _concatenate_list_of_lists([
        [person_case.case_id],
        [occurrence_child_case.case_id for occurrence_child_case in all_occurrence_cases],
        [episode_child_case.case_id for episode_child_case in all_episode_cases],
        [drtb_hiv_referral_case.case_id for drtb_hiv_referral_case in all_drtb_hiv_referral_cases],
    ])


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            'episode_case_id',
            nargs='+',
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            default=False,
            help='For unit tests only. Skips user confirmation.'
        )

    def handle(self, domain, episode_case_id, **options):
        if not options.get('noinput'):
            confirm = raw_input(
                u"""
                Are you sure you want to delete all these episodes, and their associated
                person, occurrence, and drtb-hiv-referral cases?

                Type DELETE and press Enter to confirm.
                """
            )
            if confirm != "DELETE":
                print("\n\t\tCancelled.")
                return
            else:
                print("\n\t\tDeleting...")

        migrated_case_ids = _concatenate_list_of_lists([
            _get_related_case_ids(domain, episode_id) for episode_id in episode_case_id
        ])
        CaseAccessors(domain).soft_delete_cases(migrated_case_ids)
