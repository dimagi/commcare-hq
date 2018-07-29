from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase

from casexml.apps.case.cleanup import safe_hard_delete
from casexml.apps.case.exceptions import CommCareCaseError
from casexml.apps.case.mock import CaseFactory, CaseStructure, CaseIndex
from casexml.apps.case.tests.util import TEST_DOMAIN_NAME
from corehq.apps.change_feed import topics
from corehq.form_processor.exceptions import CaseNotFound, XFormNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from corehq.form_processor.tests.utils import use_sql_backend
from corehq.form_processor.utils.general import should_use_sql_backend
from testapps.test_pillowtop.utils import capture_kafka_changes_context


class TestHardDelete(TestCase):

    def setUp(self):
        self.casedb = CaseAccessors(TEST_DOMAIN_NAME)
        self.formdb = FormAccessors(TEST_DOMAIN_NAME)

    def test_simple_delete(self):
        factory = CaseFactory()
        case = factory.create_case()
        [case] = factory.create_or_update_case(
            CaseStructure(case_id=case.case_id, attrs={'update': {'foo': 'bar'}})
        )
        self.assertIsNotNone(self.casedb.get_case(case.case_id))
        self.assertEqual(2, len(case.xform_ids))
        for form_id in case.xform_ids:
            self.assertIsNotNone(self.formdb.get_form(form_id))

        with capture_kafka_changes_context(topics.FORM_SQL, topics.CASE_SQL) as change_context:
            safe_hard_delete(case)

        if should_use_sql_backend(case.domain):
            self.assertEqual(3, len(change_context.changes))
            expected_ids = {case.case_id} | set(case.xform_ids)
            self.assertEqual(expected_ids, {change.id for change in change_context.changes})
            for change in change_context.changes:
                self.assertTrue(change.deleted)

        with self.assertRaises(CaseNotFound):
            self.casedb.get_case(case.case_id)

        for form_id in case.xform_ids:
            with self.assertRaises(XFormNotFound):
                self.formdb.get_form(form_id)

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
            safe_hard_delete(parent)

        # deleting the child is ok
        safe_hard_delete(child)
        self.assertIsNotNone(self.casedb.get_case(parent.case_id))
        with self.assertRaises(CaseNotFound):
            self.casedb.get_case(child.case_id)

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

        self.assertIsNotNone(self.casedb.get_case(c1.case_id))
        self.assertIsNotNone(self.casedb.get_case(c2.case_id))


@use_sql_backend
class TestHardDeleteSQL(TestHardDelete):
    pass
