from django.utils.unittest.case import TestCase
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import check_xml_line_by_line, CaseBlock,\
    check_user_has_case
from casexml.apps.case.util import post_case_blocks
from casexml.apps.phone.restore import generate_restore_payload
from casexml.apps.phone.xml import date_to_xml_string
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

        def create_and_test(case_id, user, owner, should_have, should_not_have):
            case_block = self.get_create_block(
                case_id=case_id,
                type="case",
                user_id=user.user_id,
                owner_id=owner.get_id,
            )
            post_case_blocks([case_block])
            CommCareCase.get(case_id)

            check_has_block(case_block, should_have, should_not_have)

        def update_and_test(case_id, owner=None, should_have=None, should_not_have=None):
            case_block = self.get_update_block(
                case_id='case-a-1',
                update={'greeting': "Hello!"},
                owner_id=owner.get_id if owner else None,
            )
            post_case_blocks([case_block])

            check_has_block(case_block, should_have, should_not_have, line_by_line=False)

        def check_has_block(case_block, should_have, should_not_have, line_by_line=True):
            for user in should_have:
                check_user_has_case(self, user.to_casexml_user(), case_block, line_by_line=line_by_line)
            for user in should_not_have:
                check_user_has_case(self, user.to_casexml_user(), case_block, should_have=False, line_by_line=line_by_line)

        create_and_test(
            case_id='case-a-1',
            user=self.userA1,
            owner=self.groupA,
            should_have=[self.userA1, self.userA2, self.userX],
            should_not_have=[self.userB1, self.userB2]
        )

        create_and_test(
            case_id='case-b-1',
            user=self.userB1,
            owner=self.groupB,
            should_have=[self.userB1, self.userB2, self.userX],
            should_not_have=[self.userA1, self.userA2]
        )

        create_and_test(
            case_id='case-a-2',
            user=self.userX,
            owner=self.groupA,
            should_have=[self.userA1, self.userA2, self.userX],
            should_not_have=[self.userB1, self.userB2]
        )

        update_and_test(
            case_id='case-a-1',
            should_have=[self.userA1, self.userA2, self.userX],
            should_not_have=[self.userB1, self.userB2],
        )

        update_and_test(
            case_id='case-a-1',
            owner=self.groupB,
            should_have=[self.userB1, self.userB2, self.userX],
            should_not_have=[self.userA1, self.userA2],
        )


    def get_create_block(self, case_id, type, user_id, owner_id, name=None, **kwargs):
        name = name or case_id
        case_block = CaseBlock(
            case_id=case_id,
            create__case_name=name,
            create__case_type_id=type,
            create__user_id=user_id,
            create__external_id=case_id,
            update={'owner_id': owner_id},
            **kwargs
        ).as_xml(format_datetime=date_to_xml_string)
        return case_block

    def get_update_block(self, case_id, owner_id=None, update=None):
        update = update or {}
        case_block = CaseBlock(
            case_id=case_id,
            update=update,
            update__owner_id=owner_id or CaseBlock.undefined,
        ).as_xml(format_datetime=date_to_xml_string)
        return case_block