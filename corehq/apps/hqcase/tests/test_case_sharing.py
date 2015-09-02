from django.test import TestCase
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import check_user_has_case
from casexml.apps.case.util import post_case_blocks
from casexml.apps.case.xml import V1, V2
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username

class CaseSharingTest(TestCase):
    def setUp(self):
        """
        Two groups A and B, with users A1, A2 and B1, B2 respectively, and supervisor X who belongs to both.
        
        """

        self.domain = "test-domain"
        create_domain(self.domain)
        password = "****"

        def create_user(username):
            return CommCareUser.create(self.domain, format_username(username, self.domain), password)

        def create_group(name, *users):
            group = Group(users=[user.user_id for user in users], name=name, domain=self.domain)
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

        def create_and_test(case_id, user, owner, should_have, should_not_have, version):
            case_block = self.get_create_block(
                case_id=case_id,
                type="case",
                user_id=user.user_id,
                owner_id=owner.get_id,
                version=version
            )
            post_case_blocks([case_block], {'domain': self.domain})
            CommCareCase.get(case_id)

            check_has_block(case_block, should_have, should_not_have, version=version)

        def update_and_test(case_id, owner=None, should_have=None, should_not_have=None, version=V1):
            case_block = self.get_update_block(
                case_id='case-a-1',
                update={'greeting': "Hello!"},
                owner_id=owner.get_id if owner else None,
                version=version
            )
            post_case_blocks([case_block], {'domain': self.domain})

            check_has_block(case_block, should_have, should_not_have, line_by_line=False, version=version)

        def check_has_block(case_block, should_have, should_not_have, line_by_line=True, version=V1):
            for user in should_have:
                check_user_has_case(self, user.to_casexml_user(), case_block, line_by_line=line_by_line, version=version)
            for user in should_not_have:
                check_user_has_case(self, user.to_casexml_user(), case_block, should_have=False, line_by_line=line_by_line, version=version)
        for version in [V2]:
            create_and_test(
                case_id='case-a-1',
                user=self.userA1,
                owner=self.groupA,
                should_have=[self.userA1, self.userA2, self.userX],
                should_not_have=[self.userB1, self.userB2],
                version=version
            )

            create_and_test(
                case_id='case-b-1',
                user=self.userB1,
                owner=self.groupB,
                should_have=[self.userB1, self.userB2, self.userX],
                should_not_have=[self.userA1, self.userA2],
                version=version
            )

            create_and_test(
                case_id='case-a-2',
                user=self.userX,
                owner=self.groupA,
                should_have=[self.userA1, self.userA2, self.userX],
                should_not_have=[self.userB1, self.userB2],
                version=version
            )

            update_and_test(
                case_id='case-a-1',
                should_have=[self.userA1, self.userA2, self.userX],
                should_not_have=[self.userB1, self.userB2],
                version=version,
            )

            update_and_test(
                case_id='case-a-1',
                owner=self.groupB,
                should_have=[self.userB1, self.userB2, self.userX],
                should_not_have=[self.userA1, self.userA2],
                version=version
            )


    def get_create_block(self, case_id, type, user_id, owner_id, name=None, version=V1, **kwargs):
        name = name or case_id
        case_block = CaseBlock(
            create=True,
            case_id=case_id,
            case_name=name,
            case_type=type,
            user_id=user_id,
            external_id=case_id,
            owner_id=owner_id,
            version=version,
            **kwargs
        ).as_xml()
        return case_block

    def get_update_block(self, case_id, owner_id=None, update=None, version=V1):
        update = update or {}
        case_block = CaseBlock(
            case_id=case_id,
            update=update,
            owner_id=owner_id or CaseBlock.undefined,
            version=version,
        ).as_xml()
        return case_block
