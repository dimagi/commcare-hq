import uuid
from django.test import SimpleTestCase
from corehq.util.global_request.api import set_request, get_request, get_request_domain
from jsonobject import JsonObject


class GlobalRequestTest(SimpleTestCase):

    def test_get_and_set(self):
        obj = object()
        set_request(obj)
        self.assertEqual(obj, get_request())

    def test_get_domain(self):
        domain = uuid.uuid4().hex
        request = JsonObject(domain=domain)
        set_request(request)
        self.assertEqual(domain, get_request_domain())

    def test_get_domain_null(self):
        set_request(None)
        self.assertEqual(None, get_request_domain())

    def tearDown(self):
        set_request(None)
        super(GlobalRequestTest, self).tearDown()
