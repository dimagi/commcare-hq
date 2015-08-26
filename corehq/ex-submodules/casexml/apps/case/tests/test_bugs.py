import uuid
from django.test import TestCase
import os
from django.test.utils import override_settings
from casexml.apps.case.exceptions import IllegalCaseId
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from casexml.apps.case.templatetags.case_tags import get_case_hierarchy
from casexml.apps.case.tests.util import delete_all_cases
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml import V2
from corehq.apps.hqcase.dbaccessors import get_total_case_count
from couchforms.tests.testutils import post_xform_to_couch
from casexml.apps.case.xform import process_cases


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class CaseBugTest(TestCase):
    """
    Tests bugs that come up in case processing
    """

    def setUp(self):
        delete_all_cases()

    def testConflictingIds(self):
        """
        If two forms share an ID it's a conflict
        """
        file_path = os.path.join(os.path.dirname(__file__), "data", "bugs", "id_conflicts.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        try:
            process_cases(form)
            self.fail("Previous statement should have raised an exception")
        except Exception:
            pass


    def testStringFormatProblems(self):
        """
        If two forms share an ID it's a conflict
        """
        file_path = os.path.join(os.path.dirname(__file__), "data", "bugs", "string_formatting.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        # before the bug was fixed this call failed
        process_cases(form)


    def testEmptyCaseId(self):
        """
        How do we do when submitting an empty case id?
        """
        file_path = os.path.join(os.path.dirname(__file__), "data", "bugs", "empty_id.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        try:
            process_cases(form)
            self.fail("Empty Id should crash")
        except:
            pass


    def _testCornerCaseDatatypeBugs(self, value):

        def _test(custom_format_args):
            case_id = uuid.uuid4().hex
            format_args = {
                'case_id': case_id,
                'form_id': uuid.uuid4().hex,
                'user_id': uuid.uuid4().hex,
                'case_name': 'data corner cases',
                'case_type': 'datatype-check',
            }
            format_args.update(custom_format_args)
            for filename in ['bugs_in_case_create_datatypes.xml', 'bugs_in_case_update_datatypes.xml']:
                file_path = os.path.join(os.path.dirname(__file__), "data", "bugs", filename)
                with open(file_path, "rb") as f:
                    xml_data = f.read()
                xml_data = xml_data.format(**format_args)
                form = post_xform_to_couch(xml_data)
                # before the bug was fixed this call failed
                process_cases(form)
                case = CommCareCase.get(case_id)
                self.assertEqual(format_args['user_id'], case.user_id)
                self.assertEqual(format_args['case_name'], case.name)
                self.assertEqual(format_args['case_type'], case.type)

        _test({'case_name': value})
        _test({'case_type': value})
        _test({'user_id': value})

    def testDateInCasePropertyBug(self):
        """
        How do we do when submitting a case name that looks like a date?
        """
        self._testCornerCaseDatatypeBugs('2011-11-16')

    def testIntegerInCasePropertyBug(self):
        """
        How do we do when submitting a case name that looks like a number?
        """
        self._testCornerCaseDatatypeBugs('42')

    def testDecimalInCasePropertyBug(self):
        """
        How do we do when submitting a case name that looks like a number?
        """
        self._testCornerCaseDatatypeBugs('4.06')

    def testDuplicateCasePropertiesBug(self):
        """
        How do we do when submitting multiple values for the same property
        in an update block
        """
        file_path = os.path.join(os.path.dirname(__file__), "data", "bugs",
                                 "duplicate_case_properties.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        # before the bug was fixed this call failed
        process_cases(form)
        case = CommCareCase.get(form.xpath("form/case/@case_id"))
        # make sure the property is there, but empty
        self.assertEqual("", case.foo)

        file_path = os.path.join(os.path.dirname(__file__), "data", "bugs",
                                 "duplicate_case_properties_2.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(form)
        case = CommCareCase.get(form.xpath("form/case/@case_id"))
        # make sure the property takes the last defined value
        self.assertEqual("2", case.bar)

    def testMultipleCaseBlocks(self):
        """
        How do we do when submitting a form with multiple blocks for the same case?
        """
        file_path = os.path.join(os.path.dirname(__file__), "data", "bugs", "multiple_case_blocks.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        # before the bug was fixed this call failed
        process_cases(form)
        case = CommCareCase.get(form.xpath("form/comunidad/case/@case_id"))
        self.assertEqual('1630005', case.community_code)
        self.assertEqual('SantaMariaCahabon', case.district_name)
        self.assertEqual('TAMERLO', case.community_name)

        ids = case.get_xform_ids_from_couch()
        self.assertEqual(1, len(ids))
        self.assertEqual(form._id, ids[0])


    def testLotsOfSubcases(self):
        """
        How do we do when submitting a form with multiple blocks for the same case?
        """
        file_path = os.path.join(os.path.dirname(__file__), "data", "bugs", "lots_of_subcases.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        # before the bug was fixed this call failed
        process_cases(form)
        self.assertEqual(11, get_total_case_count())

    def testSubmitToDeletedCase(self):
        # submitting to a deleted case should succeed and affect the case
        case_id = 'immagetdeleted'
        deleted_doc_type = 'CommCareCase-Deleted'
        post_case_blocks([
            CaseBlock(create=True, case_id=case_id, user_id='whatever',
                      version=V2, update={'foo': 'bar'}).as_xml()
        ])
        case = CommCareCase.get(case_id)
        self.assertEqual('bar', case.foo)
        # hack copy how we delete things
        case.doc_type = deleted_doc_type
        case.save()
        self.assertEqual(deleted_doc_type, case.doc_type)
        post_case_blocks([
            CaseBlock(create=False, case_id=case_id, user_id='whatever',
                      version=V2, update={'foo': 'not_bar'}).as_xml()
        ])
        case = CommCareCase.get(case_id)
        self.assertEqual('not_bar', case.foo)
        self.assertEqual(deleted_doc_type, case.doc_type)


class TestCaseHierarchy(TestCase):

    def setUp(self):
        delete_all_cases()

    def test_normal_index(self):
        cp = CommCareCase(
            _id='parent',
            name='parent',
            type='parent',
        )
        cp.save()

        cc = CommCareCase(
            _id='child',
            name='child',
            type='child',
            indices=[CommCareCaseIndex(identifier='parent', referenced_type='parent', referenced_id='parent')],
        )
        cc.save()

        hierarchy = get_case_hierarchy(cp, {})
        self.assertEqual(2, len(hierarchy['case_list']))
        self.assertEqual(1, len(hierarchy['child_cases']))

    def test_recursive_indexes(self):
        c = CommCareCase(
            _id='infinite-recursion',
            name='infinite_recursion',
            type='bug',
            indices=[CommCareCaseIndex(identifier='self', referenced_type='bug', referenced_id='infinite-recursion')],
        )
        c.save()
        # this call used to fail with infinite recursion
        hierarchy = get_case_hierarchy(c, {})
        self.assertEqual(1, len(hierarchy['case_list']))

    def test_complex_index(self):
        cp = CommCareCase(
            _id='parent',
            name='parent',
            type='parent',
        )
        cp.save()

        # cases processed according to ID order so ensure that this case is
        # processed after the task case by making its ID sort after task ID
        cc = CommCareCase(
            _id='z_goal',
            name='goal',
            type='goal',
            indices=[CommCareCaseIndex(identifier='parent', referenced_type='parent', referenced_id='parent')],
        )
        cc.save()

        cc = CommCareCase(
            _id='task1',
            name='task1',
            type='task',
            indices=[
                CommCareCaseIndex(identifier='goal', referenced_type='goal', referenced_id='z_goal'),
                CommCareCaseIndex(identifier='parent', referenced_type='parent', referenced_id='parent')
            ],
        )
        cc.save()

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
