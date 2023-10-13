import json
import uuid
from datetime import datetime, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils.http import urlencode

from django_prbac.models import Role

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.api.resources import v0_4
from corehq.apps.domain.models import Domain
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import ElasticTestMixin, es_test
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import WebUser
from corehq.form_processor.tests.utils import create_form_for_test
from corehq.util.test_utils import flag_enabled

from .utils import APIResourceTest, FakeFormESView


@es_test(requires=[form_adapter])
class TestXFormInstanceResource(APIResourceTest):
    """
    Tests the XFormInstanceResource, currently only v0_4

    TODO: Provide tests for each version, especially for those aspects
    which differ between versions. They should call into reusable tests
    for the functionality that is not different.
    """

    resource = v0_4.XFormInstanceResource

    def _submit_case_update_form(self):
        # Create an xform that touches a case
        case_id = uuid.uuid4().hex
        form = submit_case_blocks(
            CaseBlock(
                case_id=case_id,
                create=True,
            ).as_text(),
            self.domain.name
        )[0]
        form_adapter.index(
            form,
            refresh=True
        )
        return form, case_id

    def test_fetching_xform_cases(self):
        form, case_id = self._submit_case_update_form()

        # Fetch the xform through the API
        response = self._assert_auth_get_resource(self.single_endpoint(form.form_id) + "?cases__full=true")
        self.assertEqual(response.status_code, 200)
        cases = json.loads(response.content)['cases']

        # Confirm that the case appears in the resource
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]['id'], case_id)

    def test_filter_forms_by_cases_modified(self):
        form, case_id = self._submit_case_update_form()
        response = self._assert_auth_get_resource(f"{self.list_endpoint}?case_id={case_id}")
        self.assertEqual(response.status_code, 200)
        api_forms = json.loads(response.content)['objects']
        self.assertEqual(len(api_forms), 1)
        self.assertEqual(api_forms[0]['form']['case']['@case_id'], case_id)

    def _send_forms(self, forms):
        # list of form tuples [(xmlns, received_on)]
        to_ret = []
        for xmlns, received_on in forms:
            backend_form = create_form_for_test(
                xmlns=xmlns or 'fake-xmlns',
                domain=self.domain.name,
                received_on=received_on or datetime.utcnow(),
                edited_on=datetime.utcnow(),
                form_data={
                    '#type': 'fake-type',
                    '@xmlns': xmlns or 'fake-xmlns',
                    'meta': {'userID': 'metadata-user-id'},
                },
                auth_context={
                    'user_id': 'auth-user-id',
                    'domain': self.domain.name,
                    'authenticated': True,
                },
            )

            to_ret.append(backend_form)
            form_adapter.index(
                backend_form,
                refresh=True
            )
        return to_ret

    def test_get_list(self):
        """
        Any form in the appropriate domain should be in the list from the API.
        """
        xmlns = 'http://xmlns1'
        received_on = datetime(2019, 1, 2)
        self._send_forms([(xmlns, received_on)])

        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_forms = json.loads(response.content)['objects']
        self.assertEqual(len(api_forms), 1)

        api_form = api_forms[0]
        self.assertEqual(api_form['form']['@xmlns'], xmlns)
        self.assertEqual(api_form['received_on'], json_format_datetime(received_on))
        self.assertEqual(api_form['metadata']['userID'], 'metadata-user-id')
        self.assertEqual(api_form['edited_by_user_id'], 'auth-user-id')

    def test_get_by_xmlns(self):
        xmlns1 = 'https://xmlns1'

        self._send_forms([(xmlns1, None), ('https://xmlns2', None)])
        response = self._assert_auth_get_resource(
            '%s?%s' % (self.list_endpoint, urlencode({'xmlns': xmlns1})))
        self.assertEqual(response.status_code, 200)
        api_forms = json.loads(response.content)['objects']
        self.assertEqual(len(api_forms), 1)
        api_form = api_forms[0]
        self.assertEqual(api_form['form']['@xmlns'], xmlns1)

    def test_get_by_received_on(self):
        date = datetime(2019, 1, 2)
        xmlns1 = 'https://xmlns1'
        self._send_forms([(xmlns1, date), (None, datetime(2019, 3, 1))])
        params = {
            'received_on_start': datetime(2019, 1, 1).strftime("%Y-%m-%dT%H:%M:%S"),
            'received_on_end': datetime(2019, 1, 4).strftime("%Y-%m-%dT%H:%M:%S"),
        }
        response = self._assert_auth_get_resource(
            '%s?%s' % (self.list_endpoint, urlencode(params)))
        self.assertEqual(response.status_code, 200)
        api_forms = json.loads(response.content)['objects']
        self.assertEqual(len(api_forms), 1)
        api_form = api_forms[0]
        self.assertEqual(api_form['form']['@xmlns'], xmlns1)

    def test_received_on_order(self):
        date1 = datetime(2019, 1, 2)
        xmlns1 = 'https://xmlns1'
        date2 = datetime(2019, 1, 5)
        xmlns2 = 'https://xmlns2'
        self._send_forms([(xmlns1, date1), (xmlns2, date2)])

        # test asc order
        response = self._assert_auth_get_resource('%s?order_by=received_on' % self.list_endpoint)
        self.assertEqual(response.status_code, 200)
        api_forms = json.loads(response.content)['objects']
        self.assertEqual(len(api_forms), 2)
        api_form = api_forms[0]
        self.assertEqual(api_form['form']['@xmlns'], xmlns1)
        # test desc order
        response = self._assert_auth_get_resource('%s?order_by=-received_on' % self.list_endpoint)
        self.assertEqual(response.status_code, 200)
        api_forms = json.loads(response.content)['objects']
        self.assertEqual(len(api_forms), 2)
        api_form = api_forms[0]
        self.assertEqual(api_form['form']['@xmlns'], xmlns2)

    def test_get_by_indexed_on(self):
        date1 = datetime(2019, 1, 2)
        xmlns = 'https://xmlns1'
        date2 = datetime(2019, 1, 5)
        self._send_forms([(xmlns, date1), (xmlns, date2)])

        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
        response = self._assert_auth_get_resource(
            '%s?%s' % (self.list_endpoint, urlencode({'indexed_on_start': yesterday}))
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(json.loads(response.content)['objects']), 2)
        response = self._assert_auth_get_resource(
            '%s?%s' % (self.list_endpoint, urlencode({'indexed_on_end': yesterday}))
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(json.loads(response.content)['objects']), 0)

        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
        response = self._assert_auth_get_resource(
            '%s?%s' % (self.list_endpoint, urlencode({'indexed_on_start': tomorrow}))
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(json.loads(response.content)['objects']), 0)
        response = self._assert_auth_get_resource(
            '%s?%s' % (self.list_endpoint, urlencode({'indexed_on_end': tomorrow}))
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(json.loads(response.content)['objects']), 2)

    def test_archived_forms(self):
        xmlns1 = 'https://xmlns1'
        xmlns2 = 'https://xmlns2'
        forms = self._send_forms([(xmlns1, None), (xmlns2, None)])
        # archive
        update = forms[0].to_json()
        update['doc_type'] = 'xformarchived'
        form_adapter.index(
            update,
            refresh=True
        )

        # archived form should not be included by default
        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)
        api_forms = json.loads(response.content)['objects']
        self.assertEqual(len(api_forms), 1)
        api_form = api_forms[0]
        self.assertEqual(api_form['form']['@xmlns'], xmlns2)

        # archived form should be included
        response = self._assert_auth_get_resource(
            '%s?%s' % (self.list_endpoint, urlencode({'include_archived': 'true'})))
        self.assertEqual(response.status_code, 200)
        api_forms = json.loads(response.content)['objects']
        self.assertEqual(len(api_forms), 2)


@es_test
class TestXFormInstanceResourceQueries(APIResourceTest, ElasticTestMixin):
    """
    Tests that urlparameters get converted to expected ES queries.
    """
    resource = v0_4.XFormInstanceResource

    def _test_es_query(self, url_params, expected_query):

        fake_xform_es = FakeFormESView()

        prior_run_query = fake_xform_es.run_query

        # A bit of a hack since none of Python's mocking libraries seem to do basic spies easily...
        def mock_run_query(es_query):
            actual = es_query['query']['bool']['filter']
            self.checkQuery(actual, expected_query, is_raw_query=True)
            return prior_run_query(es_query)

        fake_xform_es.run_query = mock_run_query
        v0_4.MOCK_XFORM_ES = fake_xform_es

        response = self._assert_auth_get_resource('%s?%s' % (self.list_endpoint, urlencode(url_params)))
        self.assertEqual(response.status_code, 200)

    def test_get_list_xmlns(self):
        expected = [
            {'term': {'domain.exact': 'qwerty'}},
            {'term': {'doc_type': 'xforminstance'}},
            {'term': {'xmlns.exact': 'http://XMLNS'}},
            {'match_all': {}}
        ]
        self._test_es_query({'xmlns': 'http://XMLNS'}, expected)

    def test_get_list_xmlns_exact(self):
        expected = [
            {'term': {'domain.exact': 'qwerty'}},
            {'term': {'doc_type': 'xforminstance'}},
            {'term': {'xmlns.exact': 'http://XMLNS'}},
            {'match_all': {}}
        ]
        self._test_es_query({'xmlns.exact': 'http://XMLNS'}, expected)

    def test_get_list_received_on(self):
        """
        Forms can be filtered by passing ?recieved_on_start=<date>&received_on_end=<date>

        Since we not testing ElasticSearch, we only test that the proper query is generated.
        """

        start_date = datetime(1969, 6, 14)
        end_date = datetime(2011, 1, 2)
        expected = [
            {'term': {'domain.exact': 'qwerty'}},
            {'term': {'doc_type': 'xforminstance'}},
            {'range': {'received_on': {'gte': start_date.isoformat(), 'lte': end_date.isoformat()}}},
            {'match_all': {}}
        ]
        params = {
            'received_on_end': end_date.isoformat(),
            'received_on_start': start_date.isoformat(),
        }
        self._test_es_query(params, expected)

    def test_get_list_ordering(self):
        '''
        Forms can be ordering ascending or descending on received_on; by default
        ascending.
        '''

        fake_xform_es = FakeFormESView()

        # A bit of a hack since none of Python's mocking libraries seem to do basic spies easily...
        prior_run_query = fake_xform_es.run_query
        prior_count_query = fake_xform_es.count_query
        queries = []

        def mock_run_query(es_query):
            queries.append(es_query)
            return prior_run_query(es_query)

        def mock_count_query(es_query):
            queries.append(es_query)
            return prior_count_query(es_query)

        fake_xform_es.run_query = mock_run_query
        fake_xform_es.count_query = mock_count_query
        v0_4.MOCK_XFORM_ES = fake_xform_es

        # Runs *2* queries
        response = self._assert_auth_get_resource('%s?order_by=received_on' % self.list_endpoint)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(queries[0]['sort'], [{'received_on': {'missing': '_first', 'order': 'asc'}}])
        # Runs *2* queries
        response = self._assert_auth_get_resource('%s?order_by=-received_on' % self.list_endpoint)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(queries[2]['sort'], [{'received_on': {'missing': '_last', 'order': 'desc'}}])

    def test_get_list_archived(self):
        expected = [
            {
                "term": {
                    "domain.exact": "qwerty"
                }
            },
            {
                "bool": {
                    "should": [
                        {"term": {"doc_type": "xforminstance"}},
                        {"term": {"doc_type": "xformarchived"}}
                    ]
                }
            },
            {
                "match_all": {}
            }
        ]
        self._test_es_query({'include_archived': 'true'}, expected)


class TestXFormPillow(TestCase):

    def test_xformPillowTransform(self):
        """
        Test to make sure xform pillow strips the appVersion dict to match the mappings
        """
        bad_appVersion = {
            "_id": "foo",
            "domain": 'TestXFormPillow-domain',
            'received_on': "2013-09-20T01:33:12Z",
            "form": {
                "meta": {
                    "@xmlns": "http://openrosa.org/jr/xforms",
                    "username": "someuser",
                    "instanceID": "foo",
                    "userID": "some_user_id",
                    "timeEnd": "2013-09-20T01:33:12Z",
                    "appVersion": {
                        "@xmlns": "http://commcarehq.org/xforms",
                        "#text": "CCODK:\"2.5.1\"(11126). v236 CC2.5b[11126] on April-15-2013"
                    },
                    "timeStart": "2013-09-19T01:13:20Z",
                    "deviceID": "somedevice"
                }
            }
        }
        cleaned = form_adapter.to_json(bad_appVersion)
        self.assertFalse(isinstance(cleaned['form']['meta']['appVersion'], dict))
        self.assertTrue(isinstance(cleaned['form']['meta']['appVersion'], str))
        self.assertTrue(cleaned['form']['meta']['appVersion'], "CCODK:\"2.5.1\"(11126). v236 CC2.5b[11126] on April-15-2013")


class TestViewFormAttachment(TestCase):

    def setUp(self):
        super().setUp()

        Role.get_cache().clear()
        self.domain = Domain.get_or_create_with_name('qwerty', is_active=True)
        self.view_form_endpoint = self._get_view_form_endpoint()
        self.username = 'rudolph@qwerty.commcarehq.org'
        self.password = '***'
        self.user = WebUser.create(self.domain.name, self.username, self.password, None, None,
                                  email='rudoph@example.com', first_name='rudolph', last_name='commcare')
        self.user.save()

    def tearDown(self):
        self.user.delete(deleted_by_domain=self.domain.name, deleted_by=None)
        self.domain.delete()
        super(TestViewFormAttachment, self).tearDown()

    def _get_view_form_endpoint(self):
        return reverse(
            'api_form_attachment',
            kwargs=dict(
                domain=self.domain.name,
                instance_id='5321',
                attachment_id='1234',
            )
        )

    @flag_enabled('VIEW_FORM_ATTACHMENT')
    def test_domain_has_feature_flag_enabled(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.view_form_endpoint)
        # 404 status code means the request is successful, but resource is
        # not found which is OK for the purposes of this test
        self.assertEqual(response.status_code, 404)

    def test_user_has_permission(self):
        self.user.set_role(self.domain.name, 'admin')
        self.user.save()

        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.view_form_endpoint)

        # 404 status code means the request is successful, but resource is
        # not found which is OK for the purposes of this test
        self.assertEqual(response.status_code, 404)

    def test_user_has_no_permission(self):
        self.user.set_role(self.domain.name, 'none')
        self.user.save()

        self.client.login(username=self.username, password=self.password)
        response = self.client.get(self.view_form_endpoint)

        self.assertEqual(response.status_code, 403)
