from datetime import datetime
from xml.etree import ElementTree
from django.utils.unittest.case import TestCase
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import check_xml_line_by_line
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xform import extract_case_blocks
from casexml.apps.phone.models import User
from casexml.apps.phone.restore import generate_restore_payload
from casexml.apps.phone.xml import get_case_element
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username

class CaseSharingTest(TestCase):
    def setUp(self):
        """
        Two groups A and B, with users A1, A2 and B1, B2 respectively, and supervisor X who belongs to both.
        
        """

        domain = "test-domain"
        password = "****"

        def create_user(username):
            return CommCareUser.create(domain, format_username(username, domain), password)

        def create_group(name, *users):
            group = Group(users=[user.user_id for user in users], name=name, domain=domain)
            group.save()
            return group

        self.userX = create_user("X")
        self.userA1 = create_user("A1")
        self.userA2 = create_user("A2")
        self.userB1 = create_user("B1")
        self.userB2 = create_user("B2")

        self.groupA = create_group("A", self.userX, self.userA1, self.userA2)
        self.groupB = create_group("B", self.userX, self.userB1, self.userB2)

    def test_sharing(self):

        def check_user_has_case(user, case_block):
            case_block.attrib['xmlns'] = 'http://openrosa.org/http/response'
            case_block = ElementTree.fromstring(ElementTree.tostring(case_block))
            payload = ElementTree.fromstring(generate_restore_payload(user.to_casexml_user()))
            blocks = payload.findall('{http://openrosa.org/http/response}case')
            case_id = case_block.findtext('{http://openrosa.org/http/response}case_id')
            print case_id
            n = 0
            for block in blocks:
                if block.find('{http://openrosa.org/http/response}case_id') == case_id:
                    check_xml_line_by_line(self, ElementTree.tostring(block), ElementTree.tostring(case_block))
                    n += 1
                    if n == 2:
                        self.fail("Block for case_id '%s' appears twice in ota restore for user '%s'" % (case_id, user.raw_username))
            if not n:
                self.fail("Block for case_id '%s' doesn't appear in ota restore for user '%s'" % (case_id, user.raw_username))


        now = datetime.utcnow()

        case_block = get_case_element(
            CommCareCase(
                case_id="case-a-1",
                modified_on=now,
                name="case",
                type="case",
                user_id=self.userA1.user_id,
                owner_id=self.groupA.get_id,
            ),
        'create update')
        post_case_blocks([case_block])

        CommCareCase.get('case-a-1')
        
        check_user_has_case(self.userA1, case_block)
#        check_user_has_case(self.userX, case_block)
#        check_user_has_case(self.userA2, case_block)