from django.test import TestCase
from casexml.apps.case.exceptions import CommCareCaseError
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from corehq.form_processor.interfaces import FormProcessorInterface
from corehq.form_processor.exceptions import CaseNotFound, XFormNotFound


class TestHardDelete(TestCase):

    def test_simple_delete(self):
        factory = CaseFactory()
        case = factory.create_case()
        [case] = factory.create_or_update_case(CaseStructure(case_id=case._id, attrs={'update': {'foo': 'bar'}}))
        self.assertIsNotNone(FormProcessorInterface.get_case(case.id))
        self.assertEqual(2, len(case.xform_ids))
        for form_id in case.xform_ids:
            self.assertIsNotNone(FormProcessorInterface.get_xform(form_id))
        FormProcessorInterface.hard_delete_case(case)

        with self.assertRaises(CaseNotFound):
            FormProcessorInterface.get_case(case.id)

        for form_id in case.xform_ids:
            with self.assertRaises(XFormNotFound):
                FormProcessorInterface.get_xform(form_id)

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
            FormProcessorInterface.hard_delete_case(parent)

        # deleting the child is ok
        FormProcessorInterface.hard_delete_case(child)
        self.assertIsNotNone(FormProcessorInterface.get_case(parent.id))
        with self.assertRaises(CaseNotFound):
            FormProcessorInterface.get_case(child.id)

    def test_delete_sharing_form(self):
        factory = CaseFactory()
        c1, c2 = factory.create_or_update_cases([
            CaseStructure(attrs={'create': True}),
            CaseStructure(attrs={'create': True}),
        ])
        with self.assertRaises(CommCareCaseError):
            FormProcessorInterface.hard_delete_case(c1)

        with self.assertRaises(CommCareCaseError):
            FormProcessorInterface.hard_delete_case(c2)

        self.assertIsNotNone(FormProcessorInterface.get_case(c1.id))
        self.assertIsNotNone(FormProcessorInterface.get_case(c2.id))
