"""
Some utility functions for traversing case relationships used in CAS.
These utility functions assume the SQL case and form processing backend is used.
"""
from __future__ import absolute_import
from corehq.form_processor.models import CommCareCaseIndexSQL
from custom.icds.exceptions import CaseRelationshipError


def _get_exactly_one_parent_case(case, identifier, relationship, expected_parent_case_type):
    related = case.get_parent(
        identifier=identifier,
        relationship=relationship,
    )

    if len(related) != 1:
        raise CaseRelationshipError(
            "Expected exactly one parent for %s, relationship %s/%s" %
            (case.case_id, identifier, relationship)
        )

    parent_case = related[0]
    if parent_case.type != expected_parent_case_type:
        raise CaseRelationshipError(
            "Expected case type of '%s' for %s" % (expected_parent_case_type, parent_case.case_id)
        )

    return parent_case


def child_health_case_from_tasks_case(tasks_case):
    """
    This related lookup only applies for 'tasks' cases that apply to children.
    """
    if tasks_case.type != 'tasks':
        raise ValueError("Expected tasks case")

    return _get_exactly_one_parent_case(tasks_case, 'parent', CommCareCaseIndexSQL.EXTENSION, 'child_health')


def ccs_record_case_from_tasks_case(tasks_case):
    """
    This related lookup only applies for 'tasks' cases that apply to mothers.
    """
    if tasks_case.type != 'tasks':
        raise ValueError("Expected tasks case")

    return _get_exactly_one_parent_case(tasks_case, 'parent', CommCareCaseIndexSQL.EXTENSION, 'ccs_record')


def child_person_case_from_child_health_case(child_health_case):
    if child_health_case.type != 'child_health':
        raise ValueError("Expected child_health case")

    return _get_exactly_one_parent_case(child_health_case, 'parent', CommCareCaseIndexSQL.EXTENSION, 'person')


def mother_person_case_from_child_person_case(child_person_case):
    if child_person_case.type != 'person':
        raise ValueError("Expected person case")

    return _get_exactly_one_parent_case(child_person_case, 'mother', CommCareCaseIndexSQL.CHILD, 'person')


def mother_person_case_from_ccs_record_case(ccs_record_case):
    if ccs_record_case.type != 'ccs_record':
        raise ValueError("Expected ccs_record case")

    return _get_exactly_one_parent_case(ccs_record_case, 'parent', CommCareCaseIndexSQL.CHILD, 'person')


def mother_person_case_from_child_health_case(child_health_case):
    child_person_case = child_person_case_from_child_health_case(child_health_case)
    return mother_person_case_from_child_person_case(child_person_case)


def child_person_case_from_tasks_case(tasks_case):
    child_health_case = child_health_case_from_tasks_case(tasks_case)
    return child_person_case_from_child_health_case(child_health_case)
