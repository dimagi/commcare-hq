from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain

from ..models import WebUser
from ..bulk_download import make_web_user_dict


class TestBulkDownload(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain("test")
        cls.addClassCleanup(cls.domain.delete)

    def test_make_web_user_dict_with_inactive_user(self):
        user = WebUser.create("test", 'username', 'password', None, None)
        self.addCleanup(user.delete, "test", deleted_by=None)
        assert user.is_active
        user.is_active = False

        data = make_web_user_dict(user, {}, "test")
        assert data["status"] == "Inactive User"
