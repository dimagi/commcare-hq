from xml.etree import ElementTree
from casexml.apps.case.tests.util import CaseBlock, check_user_has_case
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml import V2
from casexml.apps.phone.models import User
from django.test import TestCase
class IndexTest(TestCase):
    def test_indexes(self):
        CASE_ID = 'test-index-case'
        MOTHER_CASE_ID = 'text-index-mother-case'
        FATHER_CASE_ID = 'text-index-father-case'
        USER_ID = 'test-index-user'
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
            index={'mom': ('mother-case', MOTHER_CASE_ID)},
            version=V2
        ).as_xml()

        post_case_blocks([create_index])
        check_user_has_case(self, user, create_index, version=V2)

        # Step 2. Update the case to delete <mom> and create <dad>

        update_index = CaseBlock(
            case_id=CASE_ID,
            user_id=USER_ID,
            index={'mom': ('mother-case', ''), 'dad': ('father-case', FATHER_CASE_ID)},
            version=V2
        ).as_xml()

        update_index_expected = CaseBlock(
            case_id=CASE_ID,
            user_id=USER_ID,
            create=True,
            index={'dad': ('father-case', FATHER_CASE_ID)},
            version=V2
        ).as_xml()

        post_case_blocks([update_index])

        check_user_has_case(self, user, update_index_expected, version=V2)

        # Step 3. Put <mom> back

        update_index = CaseBlock(
            case_id=CASE_ID,
            user_id=USER_ID,
            index={'mom': ('mother-case', MOTHER_CASE_ID)},
            version=V2
        ).as_xml()

        update_index_expected = CaseBlock(
            case_id=CASE_ID,
            user_id=USER_ID,
            create=True,
            index={'mom': ('mother-case', MOTHER_CASE_ID), 'dad': ('father-case', FATHER_CASE_ID)},
            version=V2
        ).as_xml()

        post_case_blocks([update_index])

        check_user_has_case(self, user, update_index_expected, version=V2)