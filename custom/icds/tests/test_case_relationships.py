from __future__ import absolute_import
from custom.icds.case_relationships import (
    child_health_case_from_tasks_case,
    ccs_record_case_from_tasks_case,
    child_person_case_from_child_health_case,
    mother_person_case_from_child_person_case,
    mother_person_case_from_ccs_record_case,
    mother_person_case_from_child_health_case,
    child_person_case_from_tasks_case,
)
from custom.icds.exceptions import CaseRelationshipError
from custom.icds.tests.base import BaseICDSTest


class CaseRelationshipTest(BaseICDSTest):
    domain = 'icds-case-relationship-test'

    @classmethod
    def setUpClass(cls):
        super(CaseRelationshipTest, cls).setUpClass()
        cls.create_basic_related_cases()

    def test_relationships(self):
        self.assertEqual(
            child_health_case_from_tasks_case(self.child_tasks_case).case_id,
            self.child_health_case.case_id
        )

        self.assertEqual(
            ccs_record_case_from_tasks_case(self.mother_tasks_case).case_id,
            self.ccs_record_case.case_id
        )

        self.assertEqual(
            child_person_case_from_child_health_case(self.child_health_case).case_id,
            self.child_person_case.case_id
        )

        self.assertEqual(
            mother_person_case_from_child_person_case(self.child_person_case).case_id,
            self.mother_person_case.case_id
        )

        self.assertEqual(
            mother_person_case_from_ccs_record_case(self.ccs_record_case).case_id,
            self.mother_person_case.case_id
        )

        self.assertEqual(
            mother_person_case_from_child_health_case(self.child_health_case).case_id,
            self.mother_person_case.case_id
        )

        self.assertEqual(
            child_person_case_from_tasks_case(self.child_tasks_case).case_id,
            self.child_person_case.case_id
        )

    def test_case_type_mismatch(self):
        with self.assertRaises(ValueError):
            child_health_case_from_tasks_case(self.child_person_case)

    def test_parent_case_type_mismatch(self):
        with self.assertRaises(CaseRelationshipError):
            child_health_case_from_tasks_case(self.mother_tasks_case)

    def test_no_parent_case(self):
        with self.assertRaises(CaseRelationshipError):
            child_health_case_from_tasks_case(self.lone_child_tasks_case)

        with self.assertRaises(CaseRelationshipError):
            ccs_record_case_from_tasks_case(self.lone_mother_tasks_case)

        with self.assertRaises(CaseRelationshipError):
            child_person_case_from_child_health_case(self.lone_child_health_case)

        with self.assertRaises(CaseRelationshipError):
            mother_person_case_from_child_person_case(self.lone_child_person_case)

        with self.assertRaises(CaseRelationshipError):
            mother_person_case_from_ccs_record_case(self.lone_ccs_record_case)
