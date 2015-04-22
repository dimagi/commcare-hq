from django.test import TestCase
from casexml.apps.case.cleanup import safe_hard_delete
from casexml.apps.case.exceptions import CommCareCaseError
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseRelationship
from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance


class TestHardDelete(TestCase):

    def test_simple_delete(self):
        factory = CaseFactory()
        case = factory.create_case()
        [case] = factory.create_or_update_case(CaseStructure(case_id=case._id, attrs={'update': {'foo': 'bar'}}))
        self.assertTrue(CommCareCase.get_db().doc_exist(case._id))
        self.assertEqual(2, len(case.xform_ids))
        for form_id in case.xform_ids:
            self.assertTrue(XFormInstance.get_db().doc_exist(form_id))
        safe_hard_delete(case)
        self.assertFalse(CommCareCase.get_db().doc_exist(case._id))
        for form_id in case.xform_ids:
            self.assertFalse(XFormInstance.get_db().doc_exist(form_id))

    def test_delete_with_related(self):
        factory = CaseFactory()
        parent = factory.create_case()
        [child] = factory.create_or_update_case(
            CaseStructure(attrs={'create': True}, walk_related=False, relationships=[
                CaseRelationship(CaseStructure(case_id=parent._id))
            ]),
        )
        # deleting the parent should not be allowed because the child still references it
        with self.assertRaises(CommCareCaseError):
            safe_hard_delete(parent)

        # deleting the child is ok
        safe_hard_delete(child)
        self.assertTrue(CommCareCase.get_db().doc_exist(parent._id))
        self.assertFalse(CommCareCase.get_db().doc_exist(child._id))

    def test_delete_sharing_form(self):
        factory = CaseFactory()
        c1, c2 = factory.create_or_update_cases([
            CaseStructure(attrs={'create': True}),
            CaseStructure(attrs={'create': True}),
        ])
        with self.assertRaises(CommCareCaseError):
            safe_hard_delete(c1)

        with self.assertRaises(CommCareCaseError):
            safe_hard_delete(c2)

        self.assertTrue(CommCareCase.get_db().doc_exist(c1._id))
        self.assertTrue(CommCareCase.get_db().doc_exist(c2._id))
