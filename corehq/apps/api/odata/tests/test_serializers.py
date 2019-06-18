from __future__ import absolute_import
from __future__ import unicode_literals

from mock import patch

from django.test import SimpleTestCase

from corehq.apps.api.odata.serializers import ODataCommCareCaseSerializer, ODataXFormInstanceSerializer


class TestODataCommCareCaseSerializer(SimpleTestCase):

    def test_update_case_json(self):
        case_json = {
            'date_closed': None,
            'domain': 'test-domain',
            'xform_ids': ['ddee0178-bce1-49cd-bf26-4d5be0fb5a27'],
            'date_modified': '2019-01-23T18:24:33.118000Z',
            'server_date_modified': '2019-01-23T18:24:33.199266Z',
            'id': '50ff9e8b-30de-4a9a-98fd-f997e7b438da',
            'opened_by': '753f34ff0856210e339878e36a0001a5',
            'server_date_opened': '2019-01-23T18:24:33.199266Z',
            'case_id': '50ff9e8b-30de-4a9a-98fd-f997e7b438da',
            'closed': False,
            'indices': {},
            'user_id': '753f34ff0856210e339878e36a0001a5',
            'indexed_on': '2019-04-29T16:03:12.434334',
            'properties': {
                'case_type': 'my_case_type',
                'owner_id': '753f34ff0856210e339878e36a0001a5',
                'external_id': None,
                'case_name': 'nick',
                'date_opened': '2019-01-23T18:24:33.118000Z',
                'included_property': 'abc'
            },
            'resource_uri': ''
        }
        with patch('corehq.apps.api.odata.serializers.get_case_type_to_properties', return_value={
            'my_case_type': ['includedproperty', 'missingproperty']
        }):
            ODataCommCareCaseSerializer().update_case_json(case_json, 'test-domain', 'my_case_type')
        self.assertEqual(case_json, {
            'date_closed': None,
            'domain': 'test-domain',
            'xform_ids': ['ddee0178-bce1-49cd-bf26-4d5be0fb5a27'],
            'date_modified': '2019-01-23T18:24:33.118000Z',
            'server_date_modified': '2019-01-23T18:24:33.199266Z',
            'opened_by': '753f34ff0856210e339878e36a0001a5',
            'server_date_opened': '2019-01-23T18:24:33.199266Z',
            'case_id': '50ff9e8b-30de-4a9a-98fd-f997e7b438da',
            'closed': False,
            'user_id': '753f34ff0856210e339878e36a0001a5',
            'properties': {
                'ownerid': '753f34ff0856210e339878e36a0001a5',
                'casetype': 'my_case_type',
                'casename': 'nick',
                'dateopened': '2019-01-23T18:24:33.118000Z',
                'includedproperty': 'abc',
                'missingproperty': None,
                'backendid': None
            }
        })
