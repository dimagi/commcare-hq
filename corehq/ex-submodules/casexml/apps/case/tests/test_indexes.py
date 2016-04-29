from collections import namedtuple
import re
from xml.etree import ElementTree
import datetime
from django.test.utils import override_settings
from casexml.apps.case.mock import CaseBlock, CaseBlockError, IndexAttrs, ChildIndexAttrs
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from casexml.apps.case.tests.util import check_user_has_case
from casexml.apps.case.util import post_case_blocks
from casexml.apps.phone.models import User
from django.test import TestCase, SimpleTestCase
from corehq.form_processor.tests.utils import FormProcessorTestUtils

USER_ID = 'test-index-user'


class IndexSimpleTest(SimpleTestCase):

    def setUp(self):
        self.i1 = CommCareCaseIndex(
            identifier='i1',
            referenced_type='t1',
            referenced_id='id1'
        )
        self.i2 = CommCareCaseIndex(
            identifier='i2',
            referenced_type='t2',
            referenced_id='id2'
        )
        self.case = CommCareCase(indices=[self.i1, self.i2])

    def testHasIndex(self):
        self.assertEqual(True, self.case.has_index('i1'))
        self.assertEqual(True, self.case.has_index('i2'))
        self.assertEqual(False, self.case.has_index('i3'))

    def testGetIndex(self):
        self.assertEqual(self.i1, self.case.get_index('i1'))
        self.assertEqual(self.i2, self.case.get_index('i2'))
        self.assertEqual(None, self.case.get_index('i3'))
        self.assertEqual(None, self.case.get_index('id1'))

    def testGetIndexByRef(self):
        self.assertEqual(self.i1, self.case.get_index_by_ref_id('id1'))
        self.assertEqual(self.i2, self.case.get_index_by_ref_id('id2'))
        self.assertEqual(None, self.case.get_index_by_ref_id('id3'))
        self.assertEqual(None, self.case.get_index_by_ref_id('i1'))

    def testRemoveIndexByRef(self):
        self.assertEqual(2, len(self.case.indices))
        self.case.remove_index_by_ref_id('id1')
        self.assertEqual(1, len(self.case.indices))
        self.assertRaises(ValueError, self.case.remove_index_by_ref_id, 'id3')
        self.assertRaises(ValueError, self.case.remove_index_by_ref_id, 'i2')


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class IndexTest(TestCase):
    CASE_ID = 'test-index-case'
    MOTHER_CASE_ID = 'text-index-mother-case'
    FATHER_CASE_ID = 'text-index-father-case'

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()

    def testIndexes(self):
        user = User(user_id=USER_ID, username="", password="", date_joined="")

        # Step 0. Create mother and father cases
        for prereq in [self.MOTHER_CASE_ID, self.FATHER_CASE_ID]:
            post_case_blocks([
                CaseBlock(create=True, case_id=prereq, user_id=USER_ID).as_xml()
            ])

        # Step 1. Create a case with index <mom>
        create_index = CaseBlock(
            create=True,
            case_id=self.CASE_ID,
            user_id=USER_ID,
            owner_id=USER_ID,
            index={'mom': ('mother-case', self.MOTHER_CASE_ID)},
        ).as_xml()

        post_case_blocks([create_index])
        check_user_has_case(self, user, create_index)

        # Step 2. Update the case to delete <mom> and create <dad>

        now = datetime.datetime.utcnow()
        update_index = CaseBlock(
            case_id=self.CASE_ID,
            user_id=USER_ID,
            index={'mom': ('mother-case', ''), 'dad': ('father-case', self.FATHER_CASE_ID)},
            date_modified=now,
        ).as_xml()

        update_index_expected = CaseBlock(
            case_id=self.CASE_ID,
            user_id=USER_ID,
            owner_id=USER_ID,
            create=True,
            index={'dad': ('father-case', self.FATHER_CASE_ID)},
            date_modified=now,
        ).as_xml()

        post_case_blocks([update_index])

        check_user_has_case(self, user, update_index_expected)

        # Step 3. Put <mom> back

        now = datetime.datetime.utcnow()
        update_index = CaseBlock(
            case_id=self.CASE_ID,
            user_id=USER_ID,
            index={'mom': ('mother-case', self.MOTHER_CASE_ID)},
            date_modified=now,
        ).as_xml()

        update_index_expected = CaseBlock(
            case_id=self.CASE_ID,
            user_id=USER_ID,
            owner_id=USER_ID,
            create=True,
            index={'mom': ('mother-case', self.MOTHER_CASE_ID),
                   'dad': ('father-case', self.FATHER_CASE_ID)},
            date_modified=now,
        ).as_xml()

        post_case_blocks([update_index])

        check_user_has_case(self, user, update_index_expected)

    def testBadIndexReferenceDomain(self):
        case_in_other_domain = self.MOTHER_CASE_ID
        parent_domain = 'parent'
        child_domain = 'child'

        post_case_blocks([
            CaseBlock(create=True, case_id=case_in_other_domain, user_id=USER_ID).as_xml()
        ], form_extras={'domain': parent_domain})

        block = CaseBlock(create=True, case_id='child-case-id', user_id=USER_ID,
                          index={'bad': ('bad-case', case_in_other_domain)})

        xform, _ = post_case_blocks([block.as_xml()],
                                    form_extras={'domain': child_domain})

        self.assertTrue(xform.is_error)
        self.assertEqual(xform.doc_type, 'XFormError')
        self.assertIn('IllegalCaseId', xform.problem)
        self.assertIn('Bad case id', xform.problem)

    def testRelationshipGetsSet(self):
        user = User(user_id=USER_ID, username="", password="", date_joined="")
        create_index = CaseBlock(
            create=True,
            case_id=self.CASE_ID,
            user_id=USER_ID,
            owner_id=USER_ID,
            index={'mom': ('mother-case', self.MOTHER_CASE_ID, 'extension')},
        ).as_xml()

        post_case_blocks([create_index])
        check_user_has_case(self, user, create_index)


class CaseBlockIndexRelationshipTests(SimpleTestCase):

    def test_case_block_index_supports_relationship(self):
        """
        CaseBlock index should allow the relationship to be set
        """
        case_block = CaseBlock(
            case_id='abcdef',
            case_type='at_risk',
            date_modified='2015-07-24',
            index={
                'host': IndexAttrs(case_type='newborn', case_id='123456', relationship='extension')
            },
        )

        self.assertEqual(
            ElementTree.tostring(case_block.as_xml()),
            re.sub(r'(\n| {2,})', '', """
            <case case_id="abcdef" date_modified="2015-07-24" xmlns="http://commcarehq.org/case/transaction/v2">
                <update>
                    <case_type>at_risk</case_type>
                </update>
                <index>
                    <host case_type="newborn" relationship="extension">123456</host>
                </index>
            </case>
            """)
        )

    def test_case_block_index_omit_child(self):
        """
        CaseBlock index relationship omit relationship attribute if set to "child"
        """
        case_block = CaseBlock(
            case_id='123456',
            case_type='newborn',
            date_modified='2015-07-24',
            index={
                'parent': IndexAttrs(case_type='mother', case_id='789abc', relationship='child')
            },
        )

        self.assertEqual(
            ElementTree.tostring(case_block.as_xml()),
            re.sub(r'(\n| {2,})', '', """
            <case case_id="123456" date_modified="2015-07-24" xmlns="http://commcarehq.org/case/transaction/v2">
                <update>
                    <case_type>newborn</case_type>
                </update>
                <index>
                    <parent case_type="mother">789abc</parent>
                </index>
            </case>
            """)
        )

    def test_case_block_index_default_relationship(self):
        """
        CaseBlock index relationship should default to "child"
        """
        case_block = CaseBlock(
            case_id='123456',
            case_type='newborn',
            date_modified='2015-07-24',
            index={
                'parent': ChildIndexAttrs(case_type='mother', case_id='789abc')
            },
        )

        self.assertEqual(
            ElementTree.tostring(case_block.as_xml()),
            re.sub(r'(\n| {2,})', '', """
            <case case_id="123456" date_modified="2015-07-24" xmlns="http://commcarehq.org/case/transaction/v2">
                <update>
                    <case_type>newborn</case_type>
                </update>
                <index>
                    <parent case_type="mother">789abc</parent>
                </index>
            </case>
            """)
        )

    def test_case_block_index_valid_relationship(self):
        """
        CaseBlock index relationship should only allow valid values
        """
        with self.assertRaisesRegexp(CaseBlockError,
                                     'Valid values for an index relationship are "child" and "extension"'):
            CaseBlock(
                case_id='abcdef',
                case_type='at_risk',
                date_modified='2015-07-24',
                index={
                    'host': IndexAttrs(case_type='newborn', case_id='123456', relationship='parent')
                },
            )
