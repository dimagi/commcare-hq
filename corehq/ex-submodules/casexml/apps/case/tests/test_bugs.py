import uuid
from couchdbkit.exceptions import BulkSaveError
from django.test import TestCase, SimpleTestCase
import os
from django.test.utils import override_settings

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseBlock, CaseFactory, CaseStructure, CaseIndex
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.templatetags.case_tags import get_case_hierarchy
from casexml.apps.case.tests.util import delete_all_cases
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml import V2, V1
from corehq.apps.receiverwrapper import submit_form_locally
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.util.test_utils import TestFileMixin


class SimpleCaseBugTests(SimpleTestCase):

    def test_generate_xml_with_no_date_modified(self):
        # before this test was added both of these calls failed
        for version in (V1, V2):
            CommCareCase(_id='test').to_xml(version)


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class CaseBugTest(TestCase, TestFileMixin):
    """
    Tests bugs that come up in case processing
    """
    file_path = ('data', 'bugs')
    root = os.path.dirname(__file__)

    def setUp(self):
        delete_all_cases()

    def test_conflicting_ids(self):
        """
        If a form and a case share an ID it's a conflict
        """
        xml_data = self.get_xml('id_conflicts')
        with self.assertRaises(BulkSaveError):
            submit_form_locally(xml_data, 'test-domain')

    @run_with_all_backends
    def test_empty_case_id(self):
        """
        Ensure that form processor fails on empty id
        """
        xml_data = self.get_xml('empty_id')
        response, form, cases = submit_form_locally(xml_data, 'test-domain')
        self.assertIn('IllegalCaseId', response.content)

    def _testCornerCaseDatatypeBugs(self, value):

        def _test(custom_format_args):
            case_id = uuid.uuid4().hex
            format_args = {
                'case_id': case_id,
                'user_id': uuid.uuid4().hex,
                'case_name': 'data corner cases',
                'case_type': 'datatype-check',
            }
            format_args.update(custom_format_args)
            for filename in ['bugs_in_case_create_datatypes', 'bugs_in_case_update_datatypes']:
                format_args['form_id'] = uuid.uuid4().hex,
                xml_data = self.get_xml(filename).format(**format_args)
                response, form, [case] = submit_form_locally(xml_data, 'test-domain')
                self.assertEqual(format_args['user_id'], case.user_id)
                self.assertEqual(format_args['case_name'], case.name)
                self.assertEqual(format_args['case_type'], case.type)

        _test({'case_name': value})
        _test({'case_type': value})
        _test({'user_id': value})

    @run_with_all_backends
    def testDateInCasePropertyBug(self):
        """
        Submits a case name/case type/user_id that looks like a date
        """
        self._testCornerCaseDatatypeBugs('2011-11-16')

    @run_with_all_backends
    def testIntegerInCasePropertyBug(self):
        """
        Submits a case name/case type/user_id that looks like a number
        """
        self._testCornerCaseDatatypeBugs('42')

    @run_with_all_backends
    def testDecimalInCasePropertyBug(self):
        """
        Submits a case name/case type/user_id that looks like a decimal
        """
        self._testCornerCaseDatatypeBugs('4.06')

    @run_with_all_backends
    def testDuplicateCasePropertiesBug(self):
        """
        Submit multiple values for the same property in an update block
        """
        xml_data = self.get_xml('duplicate_case_properties')
        response, form, [case] = submit_form_locally(xml_data, 'test-domain')
        self.assertEqual("", case.dynamic_case_properties()['foo'])

        xml_data = self.get_xml('duplicate_case_properties_2')
        response, form, [case] = submit_form_locally(xml_data, 'test-domain')
        self.assertEqual("2", case.dynamic_case_properties()['bar'])

    @run_with_all_backends
    def testMultipleCaseBlocks(self):
        """
        How do we do when submitting a form with multiple blocks for the same case?
        """
        xml_data = self.get_xml('multiple_case_blocks')
        response, form, [case] = submit_form_locally(xml_data, 'test-domain')

        self.assertEqual('1630005', case.dynamic_case_properties()['community_code'])
        self.assertEqual('SantaMariaCahabon', case.dynamic_case_properties()['district_name'])
        self.assertEqual('TAMERLO', case.dynamic_case_properties()['community_name'])

        ids = case.xform_ids
        self.assertEqual(1, len(ids))
        self.assertEqual(form.form_id, ids[0])

    @run_with_all_backends
    def testLotsOfSubcases(self):
        """
        How do we do when submitting a form with multiple blocks for the same case?
        """
        xml_data = self.get_xml('lots_of_subcases')
        response, form, cases = submit_form_locally(xml_data, 'test-domain')
        self.assertEqual(11, len(cases))

    @run_with_all_backends
    def testSubmitToDeletedCase(self):
        # submitting to a deleted case should succeed and affect the case
        case_id = 'immagetdeleted'
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


class TestCaseHierarchy(TestCase):

    def setUp(self):
        delete_all_cases()

    @run_with_all_backends
    def test_normal_index(self):
        factory = CaseFactory()
        [cp] = factory.create_or_update_case(
            CaseStructure(case_id='parent', attrs={'case_type': 'parent'})
        )

        factory.create_or_update_case(CaseStructure(
            case_id='child',
            attrs={'case_type': 'child'},
            indices=[CaseIndex(CaseStructure(case_id='parent'), related_type='parent')],
            walk_related=False
        ))

        hierarchy = get_case_hierarchy(cp, {})
        self.assertEqual(2, len(hierarchy['case_list']))
        self.assertEqual(1, len(hierarchy['child_cases']))

    @run_with_all_backends
    def test_extension_index(self):
        factory = CaseFactory()
        [case] = factory.create_or_update_case(
            CaseStructure(case_id="standard_case", attrs={'case_type': "standard_type"})
        )

        factory.create_or_update_case(
            CaseStructure(
                case_id="extension_case",
                attrs={'case_type': "extension_type"},
                indices=[
                    CaseIndex(
                        CaseStructure(case_id="standard_case"),
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

    @run_with_all_backends
    def test_recursive_indexes(self):
        factory = CaseFactory()
        [case] = factory.create_or_update_case(CaseStructure(
            case_id='infinite-recursion',
            attrs={'case_type': 'bug'},
            indices=[CaseIndex(CaseStructure(case_id='infinite-recursion'), related_type='bug')],
            walk_related=False
        ))

        # this call used to fail with infinite recursion
        hierarchy = get_case_hierarchy(case, {})
        self.assertEqual(1, len(hierarchy['case_list']))

    @run_with_all_backends
    def test_complex_index(self):
        factory = CaseFactory()
        cp = factory.create_or_update_case(CaseStructure(case_id='parent', attrs={'case_type': 'parent'}))[0]

        # cases processed according to ID order so ensure that this case is
        # processed after the task case by making its ID sort after task ID
        factory.create_or_update_case(CaseStructure(
            case_id='z_goal',
            attrs={'case_type': 'goal'},
            indices=[CaseIndex(CaseStructure(case_id='parent'), related_type='parent')],
            walk_related=False
        ))

        factory.create_or_update_case(CaseStructure(
            case_id='task1',
            attrs={'case_type': 'task'},
            indices=[
                CaseIndex(CaseStructure(case_id='z_goal'), related_type='goal', identifier='goal'),
                CaseIndex(CaseStructure(case_id='parent'), related_type='parent')
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
