import json
from unittest.mock import patch

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.linked_domain import decorators
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.users.models import HQApiKey, WebUser
from corehq.util import reverse
from corehq.util.view_utils import absolute_reverse


class RemoteAuthTest(TestCase):

    def test_returns_401_if_no_api_key(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 401)

    def test_returns_401_if_wrong_api_key(self):
        headers = {'HTTP_AUTHORIZATION': 'apikey test:wrong'}
        resp = self.client.get(self.url, **headers)

        self.assertEqual(resp.status_code, 401)

    def test_returns_403_if_valid_api_key_but_no_linked_domain_access(self):
        headers = {'HTTP_AUTHORIZATION': f'apikey test:{self.api_key.plaintext_key}'}
        with patch.object(decorators, 'can_user_access_linked_domains', return_value=False):
            resp = self.client.get(self.url, **headers)

        self.assertEqual(resp.status_code, 403)

    def test_returns_200_if_valid_api_key_and_linked_domain_access(self):
        headers = {'HTTP_AUTHORIZATION': f'apikey test:{self.api_key.plaintext_key}'}

        with patch.object(decorators, 'can_user_access_linked_domains', return_value=True):
            resp = self.client.get(self.url, **headers)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content), {'toggles': [], 'previews': []})

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.upstream_domain = 'upstream'
        cls.downstream_domain = 'downstream'
        cls.domain_obj = create_domain(cls.upstream_domain)
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.couch_user = WebUser.create(cls.upstream_domain, "test", "foobar", None, None)
        cls.addClassCleanup(cls.couch_user.delete, cls.upstream_domain, deleted_by=None)
        cls.api_key, _ = HQApiKey.objects.get_or_create(user=cls.couch_user.get_django_user())

        cls.downstream_domain_requester = absolute_reverse('domain_homepage', args=[cls.downstream_domain])
        cls.domain_link = DomainLink.link_domains(cls.downstream_domain_requester, cls.upstream_domain)

        cls.url = reverse('linked_domain:toggles', args=[cls.upstream_domain])
