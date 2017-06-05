from django.test.testcases import TestCase

from corehq.apps.users.models import DomainRequest


class TestDomainRequest(TestCase):

    def test_domain_request(self):
        requests = DomainRequest.by_domain('test')
        self.assertEqual(requests.count(), 0)
