from django.test import TestCase
from casexml.apps.case.exceptions import CommCareCaseError
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from casexml.apps.case.tests.util import TEST_DOMAIN_NAME
from corehq.form_processor.exceptions import CaseNotFound, XFormNotFound
from corehq.form_processor.interfaces.processor import FormProcessorInterface


class TestHardDelete(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.interface = FormProcessorInterface(TEST_DOMAIN_NAME)

    def test_simple_delete(self):
        factory = CaseFactory()
        case = factory.create_case()
        [case] = factory.create_or_update_case(CaseStructure(case_id=case._id, attrs={'update': {'foo': 'bar'}}))
        self.assertIsNotNone(self.interface.case_model.get(case.case_id))
        self.assertEqual(2, len(case.xform_ids))
        for form_id in case.xform_ids:
            self.assertIsNotNone(self.interface.xform_model.get(form_id))
        case.hard_delete()

        with self.assertRaises(CaseNotFound):
            self.interface.case_model.get(case.case_id)

        for form_id in case.xform_ids:
            with self.assertRaises(XFormNotFound):
                self.interface.xform_model.get(form_id)

    def test_delete_with_related(self):
        factory = CaseFactory()
        parent = factory.create_case()
        [child] = factory.create_or_update_case(
            CaseStructure(attrs={'create': True}, walk_related=False, indices=[
                CaseIndex(CaseStructure(case_id=parent.case_id))
            ]),
        )
        # deleting the parent should not be allowed because the child still references it
        with self.assertRaises(CommCareCaseError):
            parent.hard_delete()

        # deleting the child is ok
        child.hard_delete()
        self.assertIsNotNone(self.interface.case_model.get(parent.case_id))
        with self.assertRaises(CaseNotFound):
            self.interface.case_model.get(child.case_id)

    def test_delete_sharing_form(self):
        factory = CaseFactory()
        c1, c2 = factory.create_or_update_cases([
            CaseStructure(attrs={'create': True}),
            CaseStructure(attrs={'create': True}),
        ])
        with self.assertRaises(CommCareCaseError):
            c1.hard_delete()

        with self.assertRaises(CommCareCaseError):
            c2.hard_delete()

        self.assertIsNotNone(self.interface.case_model.get(c1.case_id))
        self.assertIsNotNone(self.interface.case_model.get(c2.case_id))
