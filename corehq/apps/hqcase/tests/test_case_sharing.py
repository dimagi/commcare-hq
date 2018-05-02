from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.tests.util import deprecated_check_user_has_case
from casexml.apps.case.util import post_case_blocks
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
            group = Group(users=[user.user_id for user in users], name=name, domain=self.domain,
                          case_sharing=True)
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
            post_case_blocks([case_block], {'domain': self.domain})
            check_has_block(case_block, should_have, should_not_have)

        def update_and_test(case_id, owner=None, should_have=None, should_not_have=None):
            case_block = self.get_update_block(
                case_id=case_id,
                update={'greeting': "Hello!"},
                owner_id=owner.get_id if owner else None,
            )
            post_case_blocks([case_block], {'domain': self.domain})
            check_has_block(case_block, should_have, should_not_have, line_by_line=False)

        def check_has_block(case_block, should_have, should_not_have, line_by_line=True):
            for user in should_have:
                deprecated_check_user_has_case(self, user.to_ota_restore_user(),
                    case_block, line_by_line=line_by_line)
            for user in should_not_have:
                deprecated_check_user_has_case(self, user.to_ota_restore_user(),
                    case_block, should_have=False, line_by_line=line_by_line)

        create_and_test(
            case_id='case-a-1',
            user=self.userA1,
            owner=self.groupA,
            should_have=[self.userA1, self.userA2, self.userX],
            should_not_have=[self.userB1, self.userB2],
        )

        create_and_test(
            case_id='case-b-1',
            user=self.userB1,
            owner=self.groupB,
            should_have=[self.userB1, self.userB2, self.userX],
            should_not_have=[self.userA1, self.userA2],
        )

        create_and_test(
            case_id='case-a-2',
            user=self.userX,
            owner=self.groupA,
            should_have=[self.userA1, self.userA2, self.userX],
            should_not_have=[self.userB1, self.userB2],
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
            create=True,
            case_id=case_id,
            case_name=name,
            case_type=type,
            user_id=user_id,
            external_id=case_id,
            owner_id=owner_id,
            **kwargs
        ).as_xml()
        return case_block

    def get_update_block(self, case_id, owner_id=None, update=None):
        update = update or {}
        case_block = CaseBlock(
            case_id=case_id,
            update=update,
            owner_id=owner_id or CaseBlock.undefined,
        ).as_xml()
        return case_block
