from unittest.mock import patch

from django.test import TestCase
from django.test.client import Client
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser

DOMAIN = "lookup"
USER = "test@test.com"
PASS = "password"


class LookupTableViewsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(LookupTableViewsTest, cls).setUpClass()
        cls.domain = create_domain(DOMAIN)
        cls.domain.save()
        cls.addClassCleanup(cls.domain.delete)
        cls.user = WebUser.create(DOMAIN, USER, PASS, created_by=None, created_via=None)
        cls.user.is_superuser = True
        cls.user.save()
        cls.addClassCleanup(cls.user.delete, DOMAIN, deleted_by=None)

    def test_update_tables_post_without_data_type_id(self):
        data = {
            "fields": {},
            "tag": "invalid tag",
            "is_global": False,
            "description": ""
        }
        client = Client()
        client.login(username=USER, password=PASS)
        url = reverse("update_lookup_tables", kwargs={'domain': DOMAIN})
        allow_all = patch('django_prbac.decorators.has_privilege', return_value=True)

        # Not sure why _to_kwargs doesn't work on a test client request,
        # or maybe why it does work in the real world? Mocking it was
        # the easiest way I could find to work around the issue.
        json_data = patch('corehq.apps.fixtures.views._to_kwargs', return_value=data)

        with allow_all, json_data:
            response = client.post(url, data)
        self.assertEqual(response.status_code, 200, str(response))
        self.assertIn("validation_errors", response.json())
