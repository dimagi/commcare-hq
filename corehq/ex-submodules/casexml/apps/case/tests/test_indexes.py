from xml.etree import ElementTree
import datetime
from django.test.utils import override_settings
from casexml.apps.case.exceptions import IllegalCaseId
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from casexml.apps.case.tests.util import check_user_has_case
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml import V2
from casexml.apps.phone.models import User
from django.test import TestCase, SimpleTestCase
from dimagi.utils.parsing import json_format_datetime

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
    def testIndexes(self):
        CASE_ID = 'test-index-case'
        MOTHER_CASE_ID = 'text-index-mother-case'
        FATHER_CASE_ID = 'text-index-father-case'
        user = User(user_id=USER_ID, username="", password="", date_joined="")

        # Step 0. Create mother and father cases
        for prereq in [MOTHER_CASE_ID, FATHER_CASE_ID]:
            post_case_blocks([
                CaseBlock(create=True, case_id=prereq, user_id=USER_ID,
                          version=V2).as_xml()
            ])

        # Step 1. Create a case with index <mom>
        create_index = CaseBlock(
            create=True,
            case_id=CASE_ID,
            user_id=USER_ID,
            owner_id=USER_ID,
            index={'mom': ('mother-case', MOTHER_CASE_ID)},
            version=V2
        ).as_xml(format_datetime=json_format_datetime)

        post_case_blocks([create_index])
        check_user_has_case(self, user, create_index, version=V2)

        # Step 2. Update the case to delete <mom> and create <dad>

        now = datetime.datetime.utcnow()
        update_index = CaseBlock(
            case_id=CASE_ID,
            user_id=USER_ID,
            index={'mom': ('mother-case', ''), 'dad': ('father-case', FATHER_CASE_ID)},
            version=V2,
            date_modified=now,
        ).as_xml(format_datetime=json_format_datetime)

        update_index_expected = CaseBlock(
            case_id=CASE_ID,
            user_id=USER_ID,
            owner_id=USER_ID,
            create=True,
            index={'dad': ('father-case', FATHER_CASE_ID)},
            version=V2,
            date_modified=now,
        ).as_xml(format_datetime=json_format_datetime)

        post_case_blocks([update_index])

        check_user_has_case(self, user, update_index_expected, version=V2)

        # Step 3. Put <mom> back

        now = datetime.datetime.utcnow()
        update_index = CaseBlock(
            case_id=CASE_ID,
            user_id=USER_ID,
            index={'mom': ('mother-case', MOTHER_CASE_ID)},
            version=V2,
            date_modified=now,
        ).as_xml(format_datetime=json_format_datetime)

        update_index_expected = CaseBlock(
            case_id=CASE_ID,
            user_id=USER_ID,
            owner_id=USER_ID,
            create=True,
            index={'mom': ('mother-case', MOTHER_CASE_ID),
                   'dad': ('father-case', FATHER_CASE_ID)},
            version=V2,
            date_modified=now,
        ).as_xml(format_datetime=json_format_datetime)

        post_case_blocks([update_index])

        check_user_has_case(self, user, update_index_expected, version=V2)

    def testBadIndexReference(self):
        CASE_ID = 'test-bad-index-case'
        block = CaseBlock(create=True, case_id=CASE_ID, user_id=USER_ID, version=V2,
                          index={'bad': ('bad-case', 'not-an-existing-id')})
        try:
            post_case_blocks([block.as_xml()])
            self.fail("Submitting against a bad case in an index should fail!")
        except IllegalCaseId:
            pass

    def testBadIndexReferenceDomain(self):
        case_in_other_domain = 'text-index-mother-case'
        parent_domain = 'parent'
        child_domain = 'child'

        post_case_blocks([
            CaseBlock(create=True, case_id=case_in_other_domain, user_id=USER_ID,
                      version=V2).as_xml()
        ], form_extras={'domain': parent_domain})

        block = CaseBlock(create=True, case_id='child-case-id', user_id=USER_ID, version=V2,
                          index={'bad': ('bad-case', case_in_other_domain)})

        with self.assertRaisesRegexp(IllegalCaseId, 'Bad case id'):
            post_case_blocks([block.as_xml()], form_extras={'domain': child_domain})
