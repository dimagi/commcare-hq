from uuid import uuid4

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.pillows.utils import (
    MOBILE_USER_TYPE,
    UNKNOWN_USER_TYPE,
    WEB_USER_TYPE,
    get_user_type,
)


class TestGetUserType(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = uuid4().hex
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.web_user = WebUser.create(cls.domain, 'web@example.com', '***', None, None)
        cls.addClassCleanup(cls.web_user.delete, cls.domain, deleted_by=None)
        cls.mobile_user = CommCareUser.create(
            cls.domain, f'mobile@{cls.domain}.commcarehq.org', '***', None, None)
        cls.addClassCleanup(cls.mobile_user.delete, cls.domain, deleted_by=None)
        # Groups live in the same couch db as users, and case owner ids
        # are often group ids
        cls.group = Group(domain=cls.domain, name='group')
        cls.group.save()
        cls.addClassCleanup(cls.group.delete)

    def test_web_user(self):
        assert get_user_type(self.web_user.user_id) == WEB_USER_TYPE

    def test_mobile_user(self):
        assert get_user_type(self.mobile_user.user_id) == MOBILE_USER_TYPE

    def test_group_is_unknown(self):
        assert get_user_type(self.group.get_id) == UNKNOWN_USER_TYPE

    def test_missing_doc_is_unknown(self):
        assert get_user_type(uuid4().hex) == UNKNOWN_USER_TYPE
