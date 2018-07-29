from __future__ import absolute_import
from __future__ import unicode_literals
import json
import uuid

from django.test import TestCase
from tastypie.models import ApiKey

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.linked_domain.decorators import REMOTE_REQUESTER_HEADER
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.users.models import WebUser
from corehq.util import reverse
from corehq.util.view_utils import absolute_reverse


class RemoteAuthTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(RemoteAuthTest, cls).setUpClass()

        cls.master_domain = uuid.uuid4().hex
        cls.linked_domain = uuid.uuid4().hex

        cls.domain = create_domain(cls.master_domain)
        cls.couch_user = WebUser.create(cls.master_domain, "test", "foobar")
        cls.django_user = cls.couch_user.get_django_user()
        cls.api_key, _ = ApiKey.objects.get_or_create(user=cls.django_user)

        cls.auth_headers = {'HTTP_AUTHORIZATION': 'apikey test:%s' % cls.api_key.key}

        cls.linked_domain_requester = absolute_reverse('domain_homepage', args=[cls.linked_domain])
        cls.domain_link = DomainLink.link_domains(cls.linked_domain_requester, cls.master_domain)

    @classmethod
    def tearDownClass(cls):
        cls.couch_user.delete()
        cls.api_key.delete()
        cls.domain_link.delete()
        cls.domain.delete()
        super(RemoteAuthTest, cls).tearDownClass()

    def test_remote_auth(self):
        url = reverse('linked_domain:toggles', args=[self.master_domain])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 401)

        resp = self.client.get(url, **self.auth_headers)
        self.assertEqual(resp.status_code, 400)

        headers = self.auth_headers.copy()
        headers[REMOTE_REQUESTER_HEADER] = 'wrong'
        resp = self.client.get(url, **headers)
        self.assertEqual(resp.status_code, 403)

        headers[REMOTE_REQUESTER_HEADER] = self.linked_domain_requester
        resp = self.client.get(url, **headers)
        self.assertEqual(resp.status_code, 200)
        resp_json = json.loads(resp.content)
        self.assertEqual(resp_json, {'toggles': [], 'previews': []})
