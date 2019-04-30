from __future__ import absolute_import, unicode_literals

import json

from corehq.apps.api.resources import v0_4
from corehq.motech.repeaters.models import (
    CaseRepeater,
    FormRepeater,
    ShortFormRepeater,
)

from .utils import APIResourceTest


class TestRepeaterResource(APIResourceTest):
    """
    Basic sanity checking of v0_4.RepeaterResource
    """
    resource = v0_4.RepeaterResource
    repeater_types = [FormRepeater, CaseRepeater, ShortFormRepeater]

    def test_get(self):
        # Add a repeater of various types and check that it comes back
        for cls in self.repeater_types:
            repeater = cls(domain=self.domain.name,
                           url='http://example.com/forwarding/{cls}'.format(cls=cls.__name__))
            repeater.save()
            self.addCleanup(repeater.delete)
            backend_id = repeater._id
            response = self._assert_auth_get_resource(self.single_endpoint(backend_id))
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            self.assertEqual(result['id'], backend_id)
            self.assertEqual(result['url'], repeater.url)
            self.assertEqual(result['domain'], repeater.domain)
            self.assertEqual(result['type'], cls.__name__)

    def test_get_list(self):

        # Add a form repeater and check that it comes back
        form_repeater = FormRepeater(domain=self.domain.name, url='http://example.com/forwarding/form')
        form_repeater.save()
        self.addCleanup(form_repeater.delete)
        backend_id = form_repeater._id

        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_repeaters = json.loads(response.content)['objects']
        self.assertEqual(len(api_repeaters), 1)
        self.assertEqual(api_repeaters[0]['id'], backend_id)
        self.assertEqual(api_repeaters[0]['url'], form_repeater.url)
        self.assertEqual(api_repeaters[0]['domain'], form_repeater.domain)
        self.assertEqual(api_repeaters[0]['type'], 'FormRepeater')

        # Add a case repeater and check that both come back
        case_repeater = CaseRepeater(domain=self.domain.name, url='http://example.com/forwarding/case')
        case_repeater.save()
        self.addCleanup(case_repeater.delete)
        backend_id = case_repeater._id

        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_repeaters = json.loads(response.content)['objects']
        self.assertEqual(len(api_repeaters), 2)

        api_case_repeater = [r for r in api_repeaters if r['type'] == 'CaseRepeater'][0]
        self.assertEqual(api_case_repeater['id'], case_repeater._id)
        self.assertEqual(api_case_repeater['url'], case_repeater.url)
        self.assertEqual(api_case_repeater['domain'], case_repeater.domain)

    def test_create(self):

        for cls in self.repeater_types:
            self.assertEqual(0, len(cls.by_domain(self.domain.name)))

            repeater_json = {
                "domain": self.domain.name,
                "type": cls.__name__,
                "url": "http://example.com/forwarding/{cls}".format(cls=cls.__name__),
            }
            response = self._assert_auth_post_resource(self.list_endpoint,
                                        json.dumps(repeater_json),
                                        content_type='application/json')
            self.assertEqual(response.status_code, 201, response.content)
            [repeater_back] = cls.by_domain(self.domain.name)
            self.addCleanup(repeater_back.delete)
            self.assertEqual(repeater_json['domain'], repeater_back.domain)
            self.assertEqual(repeater_json['type'], repeater_back.doc_type)
            self.assertEqual(repeater_json['url'], repeater_back.url)

    def test_update(self):

        for cls in self.repeater_types:
            repeater = cls(domain=self.domain.name,
                           url='http://example.com/forwarding/{cls}'.format(cls=cls.__name__))
            repeater.save()
            self.addCleanup(repeater.delete)
            backend_id = repeater._id
            repeater_json = {
                "domain": self.domain.name,
                "type": cls.__name__,
                "url": "http://example.com/forwarding/modified/{cls}".format(cls=cls.__name__),
            }
            response = self._assert_auth_post_resource(self.single_endpoint(backend_id),
                                                       json.dumps(repeater_json),
                                                       content_type='application/json',
                                                       method='PUT')
            self.assertEqual(response.status_code, 204, response.content)
            self.assertEqual(1, len(cls.by_domain(self.domain.name)))
            modified = cls.get(backend_id)
            self.assertTrue('modified' in modified.url)
