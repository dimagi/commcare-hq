# coding: utf-8
import uuid
from StringIO import StringIO

from django.test import TestCase
from django.test.utils import override_settings
from django.urls.base import reverse

import django_digest.test
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import normalize_username
from corehq.form_processor.utils import get_simple_form_xml
from corehq.util.test_utils import generate_cases


@override_settings(SESSION_SAVE_EVERY_REQUEST=True)
class SessionTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(SessionTest, cls).setUpClass()
        cls.domain = uuid.uuid4().hex
        cls.project = create_domain(cls.domain)
        cls.project.secure_submissions = True
        cls.project.save()

        factory = AppFactory(domain=cls.domain, build_version='2.11')
        factory.new_basic_module('open_case', 'house')
        cls.app = factory.app
        cls.app.save()

        cls.user = CommCareUser.create(
            cls.domain,
            username=normalize_username('session', cls.domain),
            password='1234',
        )

    def setUp(self):
        super(SessionTest, self).setUp()
        self.client = django_digest.test.Client()

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super(SessionTest, cls).tearDownClass()

    def test_receiver(self):
        self.client.set_authorization(self.user.username, '1234', method='Basic')
        formxml = get_simple_form_xml(uuid.uuid4().hex)
        response = self.client.post(reverse("receiver_post", args=[self.domain]), {
            "xml_submission_file": StringIO(formxml)
        })
        self.assertEqual(201, response.status_code)
        self.assertEqual(0, len(response.cookies))


@generate_cases([
    ('key_server_url', lambda test: [test.domain], 200),
    ('phone_heartbeat', lambda test: [test.domain, '123'], 200),
    ('app_download_file', lambda test: [test.domain, test.app._id, 'suite.xml'], 200),
], SessionTest)
def test_session_bypass(self, url_name, args, expected_response_code, params=None):
    args = args(self)
    url = reverse(url_name, args=args)
    self.client.set_authorization(self.user.username, '1234', method='Basic')
    response = self.client.get(url, params)
    self.assertEqual(expected_response_code, response.status_code)
    self.assertEqual(0, len(response.cookies))
