from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from couchdbkit.exceptions import BulkSaveError
from django.test import TestCase, SimpleTestCase
import os
from django.test.utils import override_settings

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseBlock, CaseFactory, CaseStructure, CaseIndex
from casexml.apps.case.models import CommCareCase
from corehq.apps.reports.view_helpers import get_case_hierarchy
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml import V2, V1
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    use_sql_backend,
)
from corehq.util.test_utils import TestFileMixin, softer_assert


class SimpleCaseBugTests(SimpleTestCase):

    def test_generate_xml_with_no_date_modified(self):
        # before this test was added both of these calls failed
        for version in (V1, V2):
            CommCareCase(_id='test').to_xml(version)


class CaseBugTestCouchOnly(TestCase):

    def test_conflicting_ids(self):
        """
        If a form and a case share an ID it's a conflict
        """
        conflict_id = uuid.uuid4().hex
        case_block = CaseBlock(
            case_id=conflict_id,
            create=True,
        ).as_string().decode('utf-8')
        with self.assertRaises(BulkSaveError):
            submit_case_blocks(case_block, 'test-conflicts', form_id=conflict_id)


class CaseBugTest(TestCase, TestFileMixin):
    """
    Tests bugs that come up in case processing
    """
    file_path = ('data', 'bugs')
    root = os.path.dirname(__file__)

    @classmethod
    def setUpClass(cls):
        super(CaseBugTest, cls).setUpClass()
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        super(CaseBugTest, cls).tearDownClass()

    def test_empty_case_id(self):
        """
        Ensure that form processor fails on empty id
        """
        case_block = CaseBlock(
            case_id='',
            create=True,
        ).as_string().decode('utf-8')
        form, cases = submit_case_blocks(case_block, 'test-domain')
        self.assertIn('IllegalCaseId', form.problem)
        self.assertEqual([], cases)  # should make no cases

    def _test_datatypes_in_various_properties(self, value):
        case_id = uuid.uuid4().hex
        create_caseblock = CaseBlock(
            case_id=case_id,
            user_id=value,
            case_name=value,
            case_type=value,
            create=True,
        ).as_string().decode('utf-8')
        update_caseblock = CaseBlock(
            case_id=case_id,
            user_id=value,
            update={
                'case_name': value,
                'case_type': value,
            }
        ).as_string().decode('utf-8')
        for caseblock in create_caseblock, update_caseblock:
            form, [case] = submit_case_blocks(caseblock, 'test-domain')
            self.assertEqual(value, case.user_id)
            self.assertEqual(value, case.name)
            self.assertEqual(value, case.type)

    def test_date_in_various_properties(self):
        """
        Submits a case name/case type/user_id that looks like a date
        """
        self._test_datatypes_in_various_properties('2011-11-16')

    def test_integer_in_various_properties(self):
        """
        Submits a case name/case type/user_id that looks like a number
        """
        self._test_datatypes_in_various_properties('42')

    def test_decimal_in_various_properties(self):
        # Submits a case name/case type/user_id that looks like a decimal
        self._test_datatypes_in_various_properties('4.06')

    def test_duplicate_case_properties(self):
        """
        Submit multiple values for the same property in an update block
        """
        case_id = '061ecbae-d9be-4bb5-bdd4-e62abd5eaf7b'
        post_case_blocks([
            CaseBlock(create=True, case_id=case_id).as_xml()
        ])
        xml_data = self.get_xml('duplicate_case_properties')
        result = submit_form_locally(xml_data, 'test-domain')
        self.assertEqual("", result.case.dynamic_case_properties()['foo'])

        xml_data = self.get_xml('duplicate_case_properties_2')
        result = submit_form_locally(xml_data, 'test-domain')
        self.assertEqual("2", result.case.dynamic_case_properties()['bar'])

    def test_multiple_case_blocks(self):
        """Ensure we can submit a form with multiple blocks for the same case"""
        case_id = uuid.uuid4().hex
        case_blocks = [
            CaseBlock(create=True, case_id=case_id, update={
                'p1': 'v1',
                'p2': 'v2',
            }).as_string().decode('utf-8'),
            CaseBlock(case_id=case_id, update={
                'p2': 'v4',
                'p3': 'v3',
            }).as_string().decode('utf-8'),
        ]
        form, [case] = submit_case_blocks(case_blocks, 'test-domain')
        self.assertEqual('v1', case.dynamic_case_properties()['p1'])
        self.assertEqual('v4', case.dynamic_case_properties()['p2'])
        self.assertEqual('v3', case.dynamic_case_properties()['p3'])

        ids = case.xform_ids
        self.assertEqual(1, len(ids))
        self.assertEqual(form.form_id, ids[0])

    def test_lots_of_subcases(self):
        """Creates a bunch of subcases"""
        # cz 2/24/2017: unclear why this test is here
        xml_data = self.get_xml('lots_of_subcases')
        result = submit_form_locally(xml_data, 'test-domain')
        self.assertEqual(11, len(result.cases))

    def test_submit_to_deleted_case(self):
        """submitting to a deleted case should succeed and affect the case"""
        case_id = uuid.uuid4().hex
        xform, [case] = post_case_blocks([
            CaseBlock(create=True, case_id=case_id, user_id='whatever',
                update={'foo': 'bar'}).as_xml()
        ])
        case.soft_delete()

        self.assertEqual('bar', case.dynamic_case_properties()['foo'])
        self.assertTrue(case.is_deleted)

        xform, [case] = post_case_blocks([
            CaseBlock(create=False, case_id=case_id, user_id='whatever',
                      update={'foo': 'not_bar'}).as_xml()
        ])
        self.assertEqual('not_bar', case.dynamic_case_properties()['foo'])
        self.assertTrue(case.is_deleted)

    def test_case_block_ordering(self):
        case_id1 = uuid.uuid4().hex
        case_id2 = uuid.uuid4().hex
        # updates before create and case blocks for different cases interleaved
        blocks = [
            CaseBlock(create=False, case_id=case_id1, update={'p': '2'}).as_xml(),
            CaseBlock(create=False, case_id=case_id2, update={'p': '2'}).as_xml(),
            CaseBlock(create=True, case_id=case_id1, update={'p': '1'}).as_xml(),
            CaseBlock(create=True, case_id=case_id2, update={'p': '1'}).as_xml()
        ]

        xform, cases = post_case_blocks(blocks)
        self.assertEqual(cases[0].get_case_property('p'), '2')
        self.assertEqual(cases[1].get_case_property('p'), '2')


@use_sql_backend
class CaseBugTestSQL(CaseBugTest):
    pass


class TestCaseHierarchy(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestCaseHierarchy, cls).setUpClass()
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        super(TestCaseHierarchy, cls).tearDownClass()

    def test_normal_index(self):
        factory = CaseFactory()
        parent_id = uuid.uuid4().hex
        [cp] = factory.create_or_update_case(
            CaseStructure(case_id=parent_id, attrs={'case_type': 'parent', 'create': True})
        )

        child_id = uuid.uuid4().hex
        factory.create_or_update_case(CaseStructure(
            case_id=child_id,
            attrs={'case_type': 'child', 'create': True},
            indices=[CaseIndex(CaseStructure(case_id=parent_id), related_type='parent')],
            walk_related=False
        ))

        hierarchy = get_case_hierarchy(cp, {})
        self.assertEqual(2, len(hierarchy['case_list']))
        self.assertEqual(1, len(hierarchy['child_cases']))

    def test_extension_index(self):
        factory = CaseFactory()
        standard_case_id = uuid.uuid4().hex
        [case] = factory.create_or_update_case(
            CaseStructure(case_id=standard_case_id, attrs={'case_type': "standard_type", 'create': True})
        )

        extension_case_id = uuid.uuid4().hex
        factory.create_or_update_case(
            CaseStructure(
                case_id=extension_case_id,
                attrs={'case_type': "extension_type", 'create': True},
                indices=[
                    CaseIndex(
                        CaseStructure(case_id=standard_case_id),
                        related_type='standard_type',
                        relationship=CASE_INDEX_EXTENSION
                    )
                ],
                walk_related=False
            )
        )

        hierarchy = get_case_hierarchy(case, {})
        self.assertEqual(2, len(hierarchy['case_list']))
        self.assertEqual(1, len(hierarchy['child_cases']))

    def test_recursive_indexes(self):
        factory = CaseFactory()
        [case] = factory.create_or_update_case(CaseStructure(
            case_id='infinite-recursion',
            attrs={'case_type': 'bug', 'create': True},
            indices=[CaseIndex(CaseStructure(case_id='infinite-recursion', attrs={'create': True}), related_type='bug')],
            walk_related=False
        ))

        # this call used to fail with infinite recursion
        hierarchy = get_case_hierarchy(case, {})
        self.assertEqual(1, len(hierarchy['case_list']))

    def test_complex_index(self):
        factory = CaseFactory()
        parent_id = uuid.uuid4().hex
        cp = factory.create_or_update_case(CaseStructure(case_id=parent_id, attrs={
            'case_type': 'parent', 'create': True
        }))[0]

        # cases processed according to ID order so ensure that this case is
        # processed after the task case by making its ID sort after task ID
        goal_id = uuid.uuid4().hex
        factory.create_or_update_case(CaseStructure(
            case_id=goal_id,
            attrs={'case_type': 'goal', 'create': True},
            indices=[CaseIndex(CaseStructure(case_id=parent_id), related_type='parent')],
            walk_related=False
        ))

        task_id = uuid.uuid4().hex
        factory.create_or_update_case(CaseStructure(
            case_id=task_id,
            attrs={'case_type': 'task', 'create': True},
            indices=[
                CaseIndex(CaseStructure(case_id=goal_id), related_type='goal', identifier='goal'),
                CaseIndex(CaseStructure(case_id=parent_id), related_type='parent')
            ],
            walk_related=False,
        ))

        # with 'ignore_relationship_types' if a case got processed along the ignored relationship first
        # then it got marked as 'seen' and would be not be processed again when it came to the correct relationship
        type_info = {
            'task': {
                'ignore_relationship_types': ['parent']
            },
        }

        hierarchy = get_case_hierarchy(cp, type_info)
        self.assertEqual(3, len(hierarchy['case_list']))
        self.assertEqual(1, len(hierarchy['child_cases']))
        self.assertEqual(2, len(hierarchy['child_cases'][0]['case_list']))
        self.assertEqual(1, len(hierarchy['child_cases'][0]['child_cases']))

    @softer_assert()
    def test_missing_transactions(self):
        # this could happen if a form was edited and resulted in a new case transaction
        # e.g. a condition on a case transaction changed
        case_id1 = uuid.uuid4().hex
        case_id2 = uuid.uuid4().hex
        form_id = uuid.uuid4().hex
        case_block = CaseBlock(
            case_id=case_id1,
            create=True,
        ).as_string().decode('utf-8')
        submit_case_blocks(case_block, 'test-transactions', form_id=form_id)
        with self.assertRaises(CaseNotFound):
            CaseAccessors().get_case(case_id2)

        # form with same ID submitted but now has a new case transaction
        new_case_block = CaseBlock(
            case_id=case_id2,
            create=True,
            case_type='t1',
        ).as_string().decode('utf-8')
        submit_case_blocks([case_block, new_case_block], 'test-transactions', form_id=form_id)
        case2 = CaseAccessors().get_case(case_id2)
        self.assertEqual([form_id], case2.xform_ids)
        self.assertEqual('t1', case2.type)


@use_sql_backend
class TestCaseHierarchySQL(TestCaseHierarchy):
    pass
