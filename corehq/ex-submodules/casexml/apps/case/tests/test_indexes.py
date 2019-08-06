from __future__ import absolute_import
from __future__ import unicode_literals
import re
import uuid
from xml.etree import cElementTree as ElementTree
import datetime
from django.test.utils import override_settings
from casexml.apps.case.mock import CaseBlock, CaseBlockError, IndexAttrs, ChildIndexAttrs
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from casexml.apps.case.tests.util import deprecated_check_user_has_case
from casexml.apps.case.util import post_case_blocks
from casexml.apps.phone.tests.utils import create_restore_user
from django.test import TestCase, SimpleTestCase
from corehq.apps.domain.models import Domain
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.form_processor.tests.utils import FormProcessorTestUtils, use_sql_backend


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


class IndexTest(TestCase):
    CASE_ID = 'test-index-case'
    MOTHER_CASE_ID = 'text-index-mother-case'
    FATHER_CASE_ID = 'text-index-father-case'

    @classmethod
    def setUpClass(cls):
        super(IndexTest, cls).setUpClass()
        delete_all_users()
        cls.project = Domain(name='index-test')
        cls.project.save()
        cls.user = create_restore_user(domain=cls.project.name)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()
        super(IndexTest, self).tearDown()

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        cls.project.delete()
        super(IndexTest, cls).tearDownClass()

    def testIndexes(self):
        # Step 0. Create mother and father cases
        for prereq in [self.MOTHER_CASE_ID, self.FATHER_CASE_ID]:
            post_case_blocks(
                [CaseBlock(create=True, case_id=prereq, user_id=self.user.user_id).as_xml()],
                domain=self.project.name
            )


        # Step 1. Create a case with index <mom>
        create_index = CaseBlock(
            create=True,
            case_id=self.CASE_ID,
            user_id=self.user.user_id,
            owner_id=self.user.user_id,
            index={'mom': ('mother-case', self.MOTHER_CASE_ID)},
        ).as_xml()

        post_case_blocks([create_index], domain=self.project.name)
        deprecated_check_user_has_case(self, self.user, create_index)

        # Step 2. Update the case to delete <mom> and create <dad>

        now = datetime.datetime.utcnow()
        update_index = CaseBlock(
            case_id=self.CASE_ID,
            user_id=self.user.user_id,
            index={'mom': ('mother-case', ''), 'dad': ('father-case', self.FATHER_CASE_ID)},
            date_modified=now,
            date_opened=now.date()
        ).as_xml()

        update_index_expected = CaseBlock(
            case_id=self.CASE_ID,
            user_id=self.user.user_id,
            owner_id=self.user.user_id,
            create=True,
            index={'dad': ('father-case', self.FATHER_CASE_ID)},
            date_modified=now,
            date_opened=now.date()
        ).as_xml()

        post_case_blocks([update_index], domain=self.project.name)

        deprecated_check_user_has_case(self, self.user, update_index_expected)

        # Step 3. Put <mom> back

        update_index = CaseBlock(
            case_id=self.CASE_ID,
            user_id=self.user.user_id,
            index={'mom': ('mother-case', self.MOTHER_CASE_ID)},
            date_modified=now,
            date_opened=now.date()
        ).as_xml()

        update_index_expected = CaseBlock(
            case_id=self.CASE_ID,
            user_id=self.user.user_id,
            owner_id=self.user.user_id,
            create=True,
            index={'mom': ('mother-case', self.MOTHER_CASE_ID),
                   'dad': ('father-case', self.FATHER_CASE_ID)},
            date_modified=now,
            date_opened=now.date()
        ).as_xml()

        post_case_blocks([update_index], domain=self.project.name)

        deprecated_check_user_has_case(self, self.user, update_index_expected)

    def testRelationshipGetsSet(self):
        parent_case_id = uuid.uuid4().hex
        post_case_blocks(
            [CaseBlock(create=True, case_id=parent_case_id, user_id=self.user.user_id).as_xml()],
            domain=self.project.name
        )
        create_index = CaseBlock(
            create=True,
            case_id=self.CASE_ID,
            user_id=self.user.user_id,
            owner_id=self.user.user_id,
            index={'mom': ('mother-case', parent_case_id, 'extension')},
        ).as_xml()
        post_case_blocks([create_index], domain=self.project.name)
        deprecated_check_user_has_case(self, self.user, create_index)


@use_sql_backend
class IndexTestSQL(IndexTest):
    pass


class CaseBlockIndexRelationshipTests(SimpleTestCase):

    def test_case_block_index_supports_relationship(self):
        """
        CaseBlock index should allow the relationship to be set
        """
        case_block = CaseBlock(
            case_id='abcdef',
            case_type='at_risk',
            date_modified='2015-07-24',
            date_opened='2015-07-24',
            index={
                'host': IndexAttrs(case_type='newborn', case_id='123456', relationship='extension')
            },
        )

        self.assertEqual(
            ElementTree.tostring(case_block.as_xml()).decode('utf-8'),
            re.sub(r'(\n| {2,})', '', """
            <case case_id="abcdef" date_modified="2015-07-24" xmlns="http://commcarehq.org/case/transaction/v2">
                <update>
                    <case_type>at_risk</case_type>
                    <date_opened>2015-07-24</date_opened>
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
            date_opened='2015-07-24',
            index={
                'parent': IndexAttrs(case_type='mother', case_id='789abc', relationship='child')
            },
        )

        self.assertEqual(
            ElementTree.tostring(case_block.as_xml()).decode('utf-8'),
            re.sub(r'(\n| {2,})', '', """
            <case case_id="123456" date_modified="2015-07-24" xmlns="http://commcarehq.org/case/transaction/v2">
                <update>
                    <case_type>newborn</case_type>
                    <date_opened>2015-07-24</date_opened>
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
            date_opened='2015-07-24',
            index={
                'parent': ChildIndexAttrs(case_type='mother', case_id='789abc')
            },
        )

        self.assertEqual(
            ElementTree.tostring(case_block.as_xml()).decode('utf-8'),
            re.sub(r'(\n| {2,})', '', """
            <case case_id="123456" date_modified="2015-07-24" xmlns="http://commcarehq.org/case/transaction/v2">
                <update>
                    <case_type>newborn</case_type>
                    <date_opened>2015-07-24</date_opened>
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
        with self.assertRaisesRegex(CaseBlockError,
                                     'Valid values for an index relationship are "child" and "extension"'):
            CaseBlock(
                case_id='abcdef',
                case_type='at_risk',
                date_modified='2015-07-24',
                index={
                    'host': IndexAttrs(case_type='newborn', case_id='123456', relationship='parent')
                },
            )
