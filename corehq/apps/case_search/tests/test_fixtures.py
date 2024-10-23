from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser

from ..fixtures import _get_template_renderer


class TestInterpolation(TestCase):
    domain_name = 'test-interpolation'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain_name)
        cls.user = WebUser.create(cls.domain_name, 'test@example.com', 'secret', None, None)
        cls.restore_user = cls.user.to_ota_restore_user(cls.domain_name)
        cls.addClassCleanup(cls.domain_obj.delete)

    def render(self, template_string):
        return _get_template_renderer(self.restore_user).render(template_string)

    def test_no_interpolation(self):
        res = self.render("dob < '2020-01-01'")
        self.assertEqual(res, "dob < '2020-01-01'")

    def test_user_id(self):
        res = self.render("@owner_id = '{user.uuid}'")
        self.assertEqual(res, f"@owner_id = '{self.user.user_id}'")
