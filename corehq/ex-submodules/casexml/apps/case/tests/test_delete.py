from django.test import TestCase
from casexml.apps.case.exceptions import CommCareCaseError
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from corehq.form_processor.interfaces.case import CaseInterface
from corehq.form_processor.exceptions import CaseNotFound, XFormNotFound
from corehq.form_processor.interfaces.xform import XFormInterface


class TestHardDelete(TestCase):

    def test_simple_delete(self):
        factory = CaseFactory()
        case = factory.create_case()
        [case] = factory.create_or_update_case(CaseStructure(case_id=case._id, attrs={'update': {'foo': 'bar'}}))
        self.assertIsNotNone(CaseInterface.get_case(case.id))
        self.assertEqual(2, len(case.xform_ids))
        for form_id in case.xform_ids:
            self.assertIsNotNone(XFormInterface.get_xform(form_id))
        CaseInterface.hard_delete(case)

        with self.assertRaises(CaseNotFound):
            CaseInterface.get_case(case.id)

        for form_id in case.xform_ids:
            with self.assertRaises(XFormNotFound):
                XFormInterface.get_xform(form_id)

    def test_delete_with_related(self):
        factory = CaseFactory()
        parent = factory.create_case()
        [child] = factory.create_or_update_case(
            CaseStructure(attrs={'create': True}, walk_related=False, indices=[
                CaseIndex(CaseStructure(case_id=parent._id))
            ]),
        )
        # deleting the parent should not be allowed because the child still references it
        with self.assertRaises(CommCareCaseError):
            CaseInterface.hard_delete(parent)

        # deleting the child is ok
        CaseInterface.hard_delete(child)
        self.assertIsNotNone(CaseInterface.get_case(parent.id))
        with self.assertRaises(CaseNotFound):
            CaseInterface.get_case(child.id)

    def test_delete_sharing_form(self):
        factory = CaseFactory()
        c1, c2 = factory.create_or_update_cases([
            CaseStructure(attrs={'create': True}),
            CaseStructure(attrs={'create': True}),
        ])
        with self.assertRaises(CommCareCaseError):
            CaseInterface.hard_delete(c1)

        with self.assertRaises(CommCareCaseError):
            CaseInterface.hard_delete(c2)

        self.assertIsNotNone(CaseInterface.get_case(c1.id))
        self.assertIsNotNone(CaseInterface.get_case(c2.id))
