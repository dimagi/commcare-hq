import simplejson
from datetime import datetime

import dateutil.parser

from django.utils.http import urlencode
from django.test import TestCase
from django.core.urlresolvers import reverse
from tastypie.exceptions import BadRequest
from tastypie.resources import Resource
from tastypie import fields
from corehq.apps.groups.models import Group
from corehq.pillows.reportxform import ReportXFormPillow

from couchforms.models import XFormInstance
from casexml.apps.case.models import CommCareCase

from corehq.pillows.xform import XFormPillow
from corehq.pillows.case import CasePillow
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.domain.models import Domain
from corehq.apps.receiverwrapper.models import FormRepeater, CaseRepeater, ShortFormRepeater
from corehq.apps.api.resources import v0_1, v0_4, v0_5
from corehq.apps.api.fields import ToManyDocumentsField, ToOneDocumentField, UseIfRequested, ToManyDictField
from corehq.apps.api import es
from corehq.apps.api.es import ESQuerySet, ESUserError
from django.conf import settings

class FakeXFormES(object):
    """
    A mock of XFormES that will return the docs that have been
    added regardless of the query.
    """
    
    def __init__(self):
        self.docs = []
        self.queries = []

    def add_doc(self, id, doc):
        self.docs.append(doc)
    
    def run_query(self, query):
        self.queries.append(query)

        start = query.get('from', 0)
        end = (query['size'] + start) if 'size' in query else None
        
        return {
            'hits': {
                'total': len(self.docs),
                'hits': [{'_source': doc} for doc in self.docs[start:end]]
            }
        }

class APIResourceTest(TestCase):
    """
    Base class for shared API tests. Sets up a domain and user and provides
    some helper methods and properties for accessing the API
    """
    resource = None # must be set by subclasses
    api_name = 'v0.4' # can be overridden by subclasses

    def setUp(self):
        self.maxDiff = None
        self.domain = Domain.get_or_create_with_name('qwerty', is_active=True)
        self.list_endpoint = reverse('api_dispatch_list',
                kwargs=dict(domain=self.domain.name,
                            api_name=self.api_name,
                            resource_name=self.resource.Meta.resource_name))
        self.username = 'rudolph@qwerty.commcarehq.org'
        self.password = '***'
        self.user = WebUser.create(self.domain.name, self.username, self.password)
        self.user.set_role(self.domain.name, 'admin')
        self.user.save()

    def tearDown(self):
        self.user.delete()
        self.domain.delete()

    def single_endpoint(self, id):
        return reverse('api_dispatch_detail', kwargs=dict(domain=self.domain.name,
                                                          api_name=self.api_name,
                                                          resource_name=self.resource.Meta.resource_name,
                                                          pk=id))


class TestXFormInstanceResource(APIResourceTest):
    """
    Tests the XFormInstanceResource, currently only v0_4

    TODO: Provide tests for each version, especially for those aspects
    which differ between versions. They should call into reusable tests
    for the functionality that is not different.
    """
    resource = v0_4.XFormInstanceResource

    def test_get_list(self):
        """
        Any form in the appropriate domain should be in the list from the API.
        """

        # The actual infrastructure involves saving to CouchDB, having PillowTop
        # read the changes and write it to ElasticSearch.

        # In order to test just the API code, we set up a fake XFormES (this should
        # really be a parameter to the XFormInstanceResource constructor)
        # and write the translated form directly; we are not trying to test
        # the ptop infrastructure.

        #the pillow is set to offline mode - elasticsearch not needed to validate
        pillow = XFormPillow(online=False)
        fake_xform_es = FakeXFormES()
        v0_4.MOCK_XFORM_ES = fake_xform_es

        backend_form = XFormInstance(xmlns = 'fake-xmlns',
                                     domain = self.domain.name,
                                     received_on = datetime.utcnow(),
                                     form = {
                                         '#type': 'fake-type',
                                         '@xmlns': 'fake-xmlns'
                                     })
        backend_form.save()
        translated_doc = pillow.change_transform(backend_form.to_json())
        fake_xform_es.add_doc(translated_doc['_id'], translated_doc)

        self.client.login(username=self.username, password=self.password)

        response = self.client.get(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_forms = simplejson.loads(response.content)['objects']
        self.assertEqual(len(api_forms), 1)

        api_form = api_forms[0]
        self.assertEqual(api_form['form']['@xmlns'], backend_form.xmlns)
        self.assertEqual(api_form['received_on'], backend_form.received_on.isoformat())

        backend_form.delete()

    def test_get_list_xmlns(self):
        """
        Forms can be filtered by passing ?xmlns=<xmlns>

        Since we not testing ElasticSearch, we only test that the proper query is generated.
        """

        fake_xform_es = FakeXFormES()

        # A bit of a hack since none of Python's mocking libraries seem to do basic spies easily...
        prior_run_query = fake_xform_es.run_query
        def mock_run_query(es_query):
            self.assertEqual(
                sorted(es_query['filter']['and']), 
                [{'term': {'doc_type': 'xforminstance'}},
                 {'term': {'domain.exact': 'qwerty'}},
                 {'term': {'xmlns.exact': 'foo'}}])
            

            return prior_run_query(es_query)
            
        fake_xform_es.run_query = mock_run_query
        v0_4.MOCK_XFORM_ES = fake_xform_es

        self.client.login(username=self.username, password=self.password)

        response = self.client.get('%s?%s' % (self.list_endpoint, urlencode({'xmlns': 'foo'})))
        self.assertEqual(response.status_code, 200)

    def test_get_list_received_on(self):
        """
        Forms can be filtered by passing ?recieved_on_start=<date>&received_on_end=<date>

        Since we not testing ElasticSearch, we only test that the proper query is generated.
        """

        fake_xform_es = FakeXFormES()
        start_date = datetime(1969, 6, 14)
        end_date = datetime(2011, 1, 2)

        # A bit of a hack since none of Python's mocking libraries seem to do basic spies easily...
        prior_run_query = fake_xform_es.run_query
        def mock_run_query(es_query):
            
            self.assertEqual(sorted(es_query['filter']['and']), [
                {'range': {'received_on': {'from': start_date.isoformat()}}},
                {'range': {'received_on': {'to': end_date.isoformat()}}},
                {'term': {'doc_type': 'xforminstance'}},
                {'term': {'domain.exact': 'qwerty'}},
            ])

            return prior_run_query(es_query)
            
        fake_xform_es.run_query = mock_run_query
        v0_4.MOCK_XFORM_ES = fake_xform_es

        self.client.login(username=self.username, password=self.password)

        response = self.client.get('%s?%s' % (self.list_endpoint, urlencode({
            'received_on_end': end_date.isoformat(),
            'received_on_start': start_date.isoformat(),
        })))

        self.assertEqual(response.status_code, 200)

    def test_get_list_ordering(self):
        '''
        Forms can be ordering ascending or descending on received_on; by default
        ascending.
        '''

        fake_xform_es = FakeXFormES()

        # A bit of a hack since none of Python's mocking libraries seem to do basic spies easily...
        prior_run_query = fake_xform_es.run_query
        queries = []
        def mock_run_query(es_query):
            queries.append(es_query)
            return prior_run_query(es_query)
            
        fake_xform_es.run_query = mock_run_query
        v0_4.MOCK_XFORM_ES = fake_xform_es

        self.client.login(username=self.username, password=self.password)

        response = self.client.get('%s?order_by=received_on' % self.list_endpoint) # Runs *2* queries
        self.assertEqual(response.status_code, 200)
        self.assertEqual(queries[0]['sort'], [{'received_on': 'asc'}])

        response = self.client.get('%s?order_by=-received_on' % self.list_endpoint) # Runs *2* queries
        self.assertEqual(response.status_code, 200)
        self.assertEqual(queries[2]['sort'], [{'received_on': 'desc'}])

class TestCommCareCaseResource(APIResourceTest):
    """
    Tests the CommCareCaseREsource, currently only v0_4
    """
    resource = v0_4.CommCareCaseResource

    def test_get_list(self):
        """
        Any case in the appropriate domain should be in the list from the API.
        """

        # The actual infrastructure involves saving to CouchDB, having PillowTop
        # read the changes and write it to ElasticSearch.

        #the pillow is set to offline mode - elasticsearch not needed to validate
        pillow = CasePillow(online=False)
        fake_case_es = FakeXFormES()
        v0_4.MOCK_CASE_ES = fake_case_es

        modify_date = datetime.utcnow()

        backend_case = CommCareCase(server_modified_on=modify_date, domain=self.domain.name)
        backend_case.save()

        translated_doc = pillow.change_transform(backend_case.to_json())
        
        fake_case_es.add_doc(translated_doc['_id'], translated_doc)

        self.client.login(username=self.username, password=self.password)

        response = self.client.get(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_cases = simplejson.loads(response.content)['objects']
        self.assertEqual(len(api_cases), 1)

        api_case = api_cases[0]
        self.assertEqual(dateutil.parser.parse(api_case['server_date_modified']), backend_case.server_modified_on)

        backend_case.delete()

class TestHOPECaseResource(APIResourceTest):
    """
    Tests the HOPECaseREsource, currently only v0_4, just to make sure
    it does not crash right away
    """
    resource = v0_4.HOPECaseResource

    def test_get_list(self):
        """
        Any case in the appropriate domain should be in the list from the API.
        """

        # The actual infrastructure involves saving to CouchDB, having PillowTop
        # read the changes and write it to ElasticSearch.

        #the pillow is set to offline mode - elasticsearch not needed to validate
        pillow = CasePillow(online=False)
        fake_case_es = FakeXFormES()
        v0_4.MOCK_CASE_ES = fake_case_es

        modify_date = datetime.utcnow()

        backend_case = CommCareCase(server_modified_on=modify_date, domain=self.domain.name)
        backend_case.save()

        translated_doc = pillow.change_transform(backend_case.to_json())

        fake_case_es.add_doc(translated_doc['_id'], translated_doc)

        self.client.login(username=self.username, password=self.password)

        response = self.client.get(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_cases = simplejson.loads(response.content)['objects']
        self.assertEqual(len(api_cases), 1)

        api_case = api_cases[0]
        self.assertEqual(dateutil.parser.parse(api_case['server_date_modified']), backend_case.server_modified_on)

        backend_case.delete()


class TestCommCareUserResource(APIResourceTest):
    """
    Basic sanity checking of v0_1.CommCareUserResource
    """
    resource = v0_5.CommCareUserResource
    api_name = 'v0.5'

    def test_get_list(self):
        self.client.login(username=self.username, password=self.password)

        commcare_user = CommCareUser.create(domain=self.domain.name, username='fake_user', password='*****')
        backend_id = commcare_user.get_id

        response = self.client.get(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_users = simplejson.loads(response.content)['objects']
        self.assertEqual(len(api_users), 1)
        self.assertEqual(api_users[0]['id'], backend_id)    

        commcare_user.delete()

    def test_get_single(self):
        self.client.login(username=self.username, password=self.password)

        commcare_user = CommCareUser.create(domain=self.domain.name, username='fake_user', password='*****')
        backend_id = commcare_user._id

        response = self.client.get(self.single_endpoint(backend_id))
        self.assertEqual(response.status_code, 200)

        api_user = simplejson.loads(response.content)
        self.assertEqual(api_user['id'], backend_id)

    def test_create(self):
        self.client.login(username=self.username, password=self.password)

        group = Group({"name": "test"})
        group.save()

        self.assertEqual(0, len(CommCareUser.by_domain(self.domain.name)))

        user_json = {
            "username": "jdoe",
            "password": "qwer1234",
            "first_name": "John",
            "last_name": "Doe",
            "email": "jdoe@example.org",
            "language": "en",
            "phone_numbers": [
                "+50253311399",
                "50253314588"
            ],
            "groups": [
                group._id
            ],
            "user_data": {
                "chw_id": "13/43/DFA"
            }
        }
        response = self.client.post(self.list_endpoint,
                                    simplejson.dumps(user_json),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 201)
        [user_back] = CommCareUser.by_domain(self.domain.name)
        self.assertEqual(user_back.username, "jdoe")
        self.assertEqual(user_back.first_name, "John")
        self.assertEqual(user_back.last_name, "Doe")
        self.assertEqual(user_back.email, "jdoe@example.org")
        self.assertEqual(user_back.language, "en")
        self.assertEqual(user_back.get_group_ids()[0], group._id)
        self.assertEqual(user_back.user_data["chw_id"], "13/43/DFA")
        self.assertEqual(user_back.default_phone_number, "+50253311399")
        user_back.delete()
        group.delete()

    def test_update(self):
        self.client.login(username=self.username, password=self.password)

        user = CommCareUser.create(domain=self.domain.name, username="test", password="qwer1234")
        group = Group({"name": "test"})
        group.save()

        user_json = {
            "first_name": "test",
            "last_name": "last",
            "email": "tlast@example.org",
            "language": "pol",
            "phone_numbers": [
                "+50253311399",
                "50253314588"
            ],
            "groups": [
                group._id
            ],
            "user_data": {
                "chw_id": "13/43/DFA"
            }
        }

        backend_id = user._id
        response = self.client.put(self.single_endpoint(backend_id),
                                   simplejson.dumps(user_json),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 204, response.content)
        self.assertEqual(1, len(CommCareUser.by_domain(self.domain.name)))
        modified = CommCareUser.get(backend_id)
        self.assertEqual(modified.username, "test")
        self.assertEqual(modified.first_name, "test")
        self.assertEqual(modified.last_name, "last")
        self.assertEqual(modified.email, "tlast@example.org")
        self.assertEqual(modified.language, "pol")
        self.assertEqual(modified.get_group_ids()[0], group._id)
        self.assertEqual(modified.user_data["chw_id"], "13/43/DFA")
        self.assertEqual(modified.default_phone_number, "+50253311399")
        modified.delete()
        group.delete()


class TestWebUserResource(APIResourceTest):
    """
    Basic sanity checking of v0_1.CommCareUserResource
    """
    resource = v0_5.WebUserResource
    api_name = 'v0.5'

    def _check_user_data(self, user, json_user):
        self.assertEqual(user._id, json_user['id'])
        role = user.get_role(self.domain.name)
        self.assertEqual(role.name, json_user['role'])
        self.assertEqual(user.is_domain_admin(self.domain.name), json_user['is_admin'])
        for perm in ['edit_web_users', 'edit_commcare_users', 'edit_data',
                     'edit_apps', 'view_reports']:
            self.assertEqual(getattr(role.permissions, perm), json_user['permissions'][perm])


    def test_get_list(self):
        self.client.login(username=self.username, password=self.password)

        response = self.client.get(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_users = simplejson.loads(response.content)['objects']
        self.assertEqual(len(api_users), 1)
        self._check_user_data(self.user, api_users[0])

        another_user = WebUser.create(self.domain.name, 'anotherguy', '***')
        another_user.set_role(self.domain.name, 'field-implementer')
        another_user.save()

        response = self.client.get(self.list_endpoint)
        self.assertEqual(response.status_code, 200)
        api_users = simplejson.loads(response.content)['objects']
        self.assertEqual(len(api_users), 2)

        # username filter
        response = self.client.get('%s?username=%s' % (self.list_endpoint, 'anotherguy'))
        self.assertEqual(response.status_code, 200)
        api_users = simplejson.loads(response.content)['objects']
        self.assertEqual(len(api_users), 1)
        self._check_user_data(another_user, api_users[0])

        response = self.client.get('%s?username=%s' % (self.list_endpoint, 'nomatch'))
        self.assertEqual(response.status_code, 200)
        api_users = simplejson.loads(response.content)['objects']
        self.assertEqual(len(api_users), 0)


    def test_get_single(self):
        self.client.login(username=self.username, password=self.password)

        response = self.client.get(self.single_endpoint(self.user._id))
        self.assertEqual(response.status_code, 200)

        api_user = simplejson.loads(response.content)
        self._check_user_data(self.user, api_user)

    def test_create(self):
        self.client.login(username=self.username, password=self.password)

        user_json = {
            "username":"test_1234",
            "password":"qwer1234",
            "email":"admin@example.com",
            "first_name":"Joe",
            "is_admin": True,
            "last_name":"Admin",
            "permissions":{
                "edit_apps":True,
                "edit_commcare_users":True,
                "edit_data":True,
                "edit_web_users":True,
                "view_reports":True
            },
            "phone_numbers":[
            ],
            "role":"admin"
        }
        response = self.client.post(self.list_endpoint,
                                    simplejson.dumps(user_json),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 201)
        user_back = WebUser.get_by_username("test_1234")
        self.assertEqual(user_back.username, "test_1234")
        self.assertEqual(user_back.first_name, "Joe")
        self.assertEqual(user_back.last_name, "Admin")
        self.assertEqual(user_back.email, "admin@example.com")
        user_back.delete()

    def test_update(self):
        self.client.login(username=self.username, password=self.password)

        user = WebUser.create(domain=self.domain.name, username="test", password="qwer1234")

        user_json = {
            "email":"admin@example.com",
            "first_name":"Joe",
            "is_admin": True,
            "last_name":"Admin",
            "permissions":{
                "edit_apps":True,
                "edit_commcare_users":True,
                "edit_data":True,
                "edit_web_users":True,
                "view_reports":True
            },
            "phone_numbers":[
            ],
            "role":"admin"
        }

        backend_id = user._id
        response = self.client.put(self.single_endpoint(backend_id),
                                   simplejson.dumps(user_json),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 204, response.content)
        modified = WebUser.get(backend_id)
        self.assertEqual(modified.username, "test")
        self.assertEqual(modified.first_name, "Joe")
        self.assertEqual(modified.last_name, "Admin")
        self.assertEqual(modified.email, "admin@example.com")
        modified.delete()

class TestRepeaterResource(APIResourceTest):
    """
    Basic sanity checking of v0_4.RepeaterResource
    """
    resource = v0_4.RepeaterResource
    repeater_types = [FormRepeater, CaseRepeater, ShortFormRepeater]

    def test_get(self):
        self.client.login(username=self.username, password=self.password)
        # Add a repeater of various types and check that it comes back
        for cls in self.repeater_types:
            repeater = cls(domain=self.domain.name,
                           url='http://example.com/forwarding/{cls}'.format(cls=cls.__name__))
            repeater.save()
            backend_id = repeater._id
            response = self.client.get(self.single_endpoint(backend_id))
            self.assertEqual(response.status_code, 200)
            result = simplejson.loads(response.content)
            self.assertEqual(result['id'], backend_id)
            self.assertEqual(result['url'], repeater.url)
            self.assertEqual(result['domain'], repeater.domain)
            self.assertEqual(result['type'], cls.__name__)
            repeater.delete()

    def test_get_list(self):
        self.client.login(username=self.username, password=self.password)

        # Add a form repeater and check that it comes back
        form_repeater = FormRepeater(domain=self.domain.name, url='http://example.com/forwarding/form')
        form_repeater.save()
        backend_id = form_repeater._id

        response = self.client.get(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_repeaters = simplejson.loads(response.content)['objects']
        self.assertEqual(len(api_repeaters), 1)
        self.assertEqual(api_repeaters[0]['id'], backend_id)
        self.assertEqual(api_repeaters[0]['url'], form_repeater.url)
        self.assertEqual(api_repeaters[0]['domain'], form_repeater.domain)
        self.assertEqual(api_repeaters[0]['type'], 'FormRepeater')

        # Add a case repeater and check that both come back
        case_repeater = CaseRepeater(domain=self.domain.name, url='http://example.com/forwarding/case')
        case_repeater.save()
        backend_id = case_repeater._id

        response = self.client.get(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_repeaters = simplejson.loads(response.content)['objects']
        self.assertEqual(len(api_repeaters), 2)

        api_case_repeater = filter(lambda r: r['type'] == 'CaseRepeater', api_repeaters)[0]
        self.assertEqual(api_case_repeater['id'], case_repeater._id)
        self.assertEqual(api_case_repeater['url'], case_repeater.url)    
        self.assertEqual(api_case_repeater['domain'], case_repeater.domain)    

        form_repeater.delete()
        case_repeater.delete()

    def test_create(self):
        self.client.login(username=self.username, password=self.password)

        for cls in self.repeater_types:
            self.assertEqual(0, len(cls.by_domain(self.domain.name)))

            repeater_json = {
                "domain": self.domain.name,
                "type": cls.__name__,
                "url": "http://example.com/forwarding/{cls}".format(cls=cls.__name__),
            }
            response = self.client.post(self.list_endpoint,
                                        simplejson.dumps(repeater_json),
                                        content_type='application/json')
            self.assertEqual(response.status_code, 201, response.content)
            [repeater_back] = cls.by_domain(self.domain.name)
            self.assertEqual(repeater_json['domain'], repeater_back.domain)
            self.assertEqual(repeater_json['type'], repeater_back.doc_type)
            self.assertEqual(repeater_json['url'], repeater_back.url)
            repeater_back.delete()


    def test_update(self):
        self.client.login(username=self.username, password=self.password)

        for cls in self.repeater_types:
            repeater = cls(domain=self.domain.name,
                           url='http://example.com/forwarding/{cls}'.format(cls=cls.__name__))
            repeater.save()
            backend_id = repeater._id
            repeater_json = {
                "domain": self.domain.name,
                "type": cls.__name__,
                "url": "http://example.com/forwarding/modified/{cls}".format(cls=cls.__name__),
            }
            response = self.client.put(self.single_endpoint(backend_id),
                                       simplejson.dumps(repeater_json),
                                       content_type='application/json')
            self.assertEqual(response.status_code, 204, response.content)
            self.assertEqual(1, len(cls.by_domain(self.domain.name)))
            modified = cls.get(backend_id)
            self.assertTrue('modified' in modified.url)
            repeater.delete()

class TestReportPillow(TestCase):
    def test_xformPillowTransform(self):
        """
        Test to make sure report xform and reportxform pillows strip the appVersion dict to match the
        mappings
        """
        pillows = [ReportXFormPillow(online=False),XFormPillow(online=False)]
        bad_appVersion = {
            "_id": "foo",
            "domain": settings.ES_XFORM_FULL_INDEX_DOMAINS[0],
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
        for pillow in pillows:
            cleaned = pillow.change_transform(bad_appVersion)
            self.assertFalse(isinstance(cleaned['form']['meta']['appVersion'], dict))
            self.assertTrue(isinstance(cleaned['form']['meta']['appVersion'], str))
            self.assertTrue(cleaned['form']['meta']['appVersion'], "CCODK:\"2.5.1\"(11126). v236 CC2.5b[11126] on April-15-2013")


class TestESQuerySet(TestCase):
    '''
    Tests the ESQuerySet for appropriate slicing, etc
    '''

    def test_slice(self):
        es = FakeXFormES()
        for i in xrange(0, 1300):
            es.add_doc(i, {'i': i})
        
        queryset = ESQuerySet(es_client=es, payload={})
        qs_slice = list(queryset[3:7])

        self.assertEqual(es.queries[0]['from'], 3)
        self.assertEqual(es.queries[0]['size'], 4)
        self.assertEqual(len(qs_slice), 4)

        queryset = ESQuerySet(es_client=es, payload={})
        qs_slice = list(queryset[10:20])

        self.assertEqual(es.queries[1]['from'], 10)
        self.assertEqual(es.queries[1]['size'], 10)
        self.assertEqual(len(qs_slice), 10)

        queryset = ESQuerySet(es_client=es, payload={})
        qs_slice = list(queryset[500:1000])
        
        self.assertEqual(es.queries[2]['from'], 500)
        self.assertEqual(es.queries[2]['size'], 500)
        self.assertEqual(len(qs_slice), 500)

    def test_order_by(self):
        es = FakeXFormES()
        for i in xrange(0, 1300):
            es.add_doc(i, {'i': i})
        
        queryset = ESQuerySet(es_client=es, payload={})
        qs_asc = list(queryset.order_by('foo'))
        self.assertEqual(es.queries[0]['sort'], [{'foo': 'asc'}])

        qs_desc = list(queryset.order_by('-foo'))
        self.assertEqual(es.queries[1]['sort'], [{'foo': 'desc'}])

        qs_overwrite = list(queryset.order_by('bizzle').order_by('-baz'))
        self.assertEqual(es.queries[2]['sort'], [{'baz': 'desc'}])

        qs_multi = list(queryset.order_by('one', '-two', 'three'))
        self.assertEqual(es.queries[3]['sort'], [{'one': 'asc'}, {'two': 'desc'}, {'three': 'asc'}])


class ToManySourceModel(object):
    def __init__(self, other_model_ids, other_model_dict):
        self.other_model_dict = other_model_dict
        self.other_model_ids = other_model_ids

    @property
    def other_models(self):
        return [self.other_model_dict.get(id) for id in self.other_model_ids]
    
class ToManyDestModel(object):
    def __init__(self, id):
        self.id = id
    
class ToManySourceResource(Resource):
    other_model_ids = fields.ListField(attribute='other_model_ids')
    other_models = ToManyDocumentsField('corehq.apps.api.tests.ToManyDestResource', attribute='other_models')

    def __init__(self, objs):
        super(ToManySourceResource, self).__init__()
        self.objs = objs

    def obj_get_list(self):
        return self.objs

    class Meta:
        model_class = ToManySourceModel

class ToManyDestResource(Resource):
    id = fields.CharField(attribute='id')

    class Meta:
        model_class = ToManyDestModel

class TestToManyDocumentsField(TestCase):
    '''
    Basic test that ToMany dehydrated alright
    '''
    
    def test_requested_use_in(self):
        dest_objs = {
            'foo': ToManyDestModel('foo'),
            'bar': ToManyDestModel('bar'),
            'baz': ToManyDestModel('baz'),
        }
        
        source_objs = [
            ToManySourceModel(other_model_ids=['foo', 'bar'], other_model_dict=dest_objs),
            ToManySourceModel(other_model_ids=['bar', 'baz'], other_model_dict=dest_objs)
        ]

        source_resource = ToManySourceResource(source_objs)

        bundle = source_resource.build_bundle(obj=source_objs[0])
        dehydrated_bundle = source_resource.full_dehydrate(bundle)

        self.assertTrue('other_models' in dehydrated_bundle.data)
        self.assertEqual([other['id'] for other in dehydrated_bundle.data['other_models']], ['foo', 'bar'])

        bundle = source_resource.build_bundle(obj=source_objs[1])
        dehydrated_bundle = source_resource.full_dehydrate(bundle)

        self.assertEqual([other['id'] for other in dehydrated_bundle.data['other_models']], ['bar', 'baz'])

        
class ToManyDictSourceModel(object):
    def __init__(self, other_model_ids, other_model_dict):
        self.other_model_dict = other_model_dict
        self.other_model_ids = other_model_ids

    @property
    def other_models(self):
        return dict([(key, self.other_model_dict.get(id)) for key, id in self.other_model_ids.items()])
    
class ToManyDictDestModel(object):
    def __init__(self, id):
        self.id = id

class ToManyDictSourceResource(Resource):
    other_model_ids = fields.ListField(attribute='other_model_ids')
    other_models = ToManyDictField('corehq.apps.api.tests.ToManyDictDestResource', attribute='other_models')

    def __init__(self, objs):
        super(ToManyDictSourceResource, self).__init__()
        self.objs = objs

    def obj_get_list(self):
        return self.objs

    class Meta:
        model_class = ToManyDictSourceModel

class ToManyDictDestResource(Resource):
    id = fields.CharField(attribute='id')

    class Meta:
        model_class = ToManyDictDestModel

class TestToManyDictField(TestCase):
    '''
    Basic test that ToMany dehydrated alright
    '''
    
    def test_dehydrate(self):
        dest_objs = {
            'foo': ToManyDictDestModel('foo'),
            'bar': ToManyDictDestModel('bar'),
            'baz': ToManyDictDestModel('baz'),
        }
        
        source_objs = [
            ToManyDictSourceModel(other_model_ids={ 'first_other': 'foo', 'second_other': 'bar'}, other_model_dict=dest_objs),
            ToManyDictSourceModel(other_model_ids={ 'first_other': 'bar', 'second_other': 'baz'}, other_model_dict=dest_objs)
        ]

        source_resource = ToManyDictSourceResource(source_objs)

        bundle = source_resource.build_bundle(obj=source_objs[0])
        dehydrated_bundle = source_resource.full_dehydrate(bundle)

        self.assertTrue('other_models' in dehydrated_bundle.data)
        self.assertEqual(dehydrated_bundle.data['other_models']['first_other']['id'] , 'foo')
        self.assertEqual(dehydrated_bundle.data['other_models']['second_other']['id'], 'bar')

        bundle = source_resource.build_bundle(obj=source_objs[1])
        dehydrated_bundle = source_resource.full_dehydrate(bundle)

        self.assertEqual(dehydrated_bundle.data['other_models']['first_other']['id'] , 'bar')
        self.assertEqual(dehydrated_bundle.data['other_models']['second_other']['id'], 'baz')



class ToOneSourceModel(object):
    def __init__(self, other_model_id, other_model_dict):
        self.other_model_dict = other_model_dict
        self.other_model_id = other_model_id

    @property
    def other_model(self):
        return self.other_model_dict.get(self.other_model_id)
    
class ToOneDestModel(object):
    def __init__(self, id):
        self.id = id
    
class ToOneSourceResource(Resource):
    other_model_id = fields.ListField(attribute='other_model_id')
    other_model = ToOneDocumentField('corehq.apps.api.tests.ToOneDestResource', attribute='other_model')

    def __init__(self, objs):
        super(ToOneSourceResource, self).__init__()
        self.objs = objs

    def obj_get_list(self):
        return self.objs

    class Meta:
        model_class = ToOneSourceModel

class ToOneDestResource(Resource):
    id = fields.CharField(attribute='id')

    class Meta:
        model_class = ToOneDestModel

class TestToOneDocumentField(TestCase):
    '''
    Basic test of the <fieldname>__full
    '''
    
    def test_requested_use_in(self):
        dest_objs = {
            'foo': ToOneDestModel('foo'),
            'bar': ToOneDestModel('bar'),
            'baz': ToOneDestModel('baz'),
        }
        
        source_objs = [
            ToOneSourceModel(other_model_id='foo', other_model_dict=dest_objs),
            ToOneSourceModel(other_model_id='bar', other_model_dict=dest_objs)
        ]

        source_resource = ToOneSourceResource(source_objs)

        bundle = source_resource.build_bundle(obj=source_objs[0])
        dehydrated_bundle = source_resource.full_dehydrate(bundle)

        self.assertEqual(dehydrated_bundle.data['other_model']['id'], 'foo')

        bundle = source_resource.build_bundle(obj=source_objs[1])
        dehydrated_bundle = source_resource.full_dehydrate(bundle)

        self.assertEqual(dehydrated_bundle.data['other_model']['id'], 'bar')

        
class UseIfRequestedModel(object):
    def __init__(self, id):
        self.id = id

class UseIfRequestedTestResource(Resource):
    something = UseIfRequested(fields.CharField(attribute='id'))

    def __init__(self, objs):
        super(UseIfRequestedTestResource, self).__init__()
        self.objs = objs

    def obj_get_list(self):
        return self.objs

    class Meta:
        model_class = UseIfRequestedModel

class TestUseIfRequested(TestCase):
    def test_requested_use_in(self):
        objs = [
            UseIfRequestedModel(id='foo'),
            UseIfRequestedModel(id='bar')
        ]

        test_resource = UseIfRequestedTestResource(objs)

        bundle = test_resource.build_bundle(obj=objs[0])
        dehydrated_bundle = test_resource.full_dehydrate(bundle)

        self.assertFalse('id' in dehydrated_bundle.data)

        bundle = test_resource.build_bundle(obj=objs[0])
        bundle.request.GET['something__full'] = 'true'
        dehydrated_bundle = test_resource.full_dehydrate(bundle)

        self.assertTrue('something' in dehydrated_bundle.data)
        self.assertEqual(dehydrated_bundle.data['something'], 'foo')


class TestSingleSignOnResource(APIResourceTest):
    resource = v0_4.SingleSignOnResource

    def setUp(self):
        super(TestSingleSignOnResource, self).setUp()
        self.commcare_username = 'webby@qwerty.commcarehq.org'
        self.commcare_password = '*****'
        self.commcare_user = CommCareUser.create(self.domain.name, self.commcare_username, self.commcare_password)

    def tearDown(self):
        self.commcare_user.delete()
        super(TestSingleSignOnResource, self).tearDown()

    def test_web_user_success(self):
        '''
        If correct credentials for a web user are submitted, the response is the profile of that web user
        '''
        response = self.client.post(self.list_endpoint, {'username': self.username, 'password': self.password})
        self.assertEqual(response.status_code, 200)

    def test_commcare_user_success(self):
        '''
        If correct credentials for a commcare user are submitted, the response is the record for that commcare user
        '''
        response = self.client.post(self.list_endpoint, {'username': self.commcare_username, 'password': self.commcare_password})
        self.assertEqual(response.status_code, 200)

    def test_wrong_domain(self):
        '''
        If correct credentials for a user in a different domain are submitted, the response is forbidden
        '''
        wrong_domain = Domain.get_or_create_with_name('dvorak', is_active=True)
        wrong_list_endpoint = reverse('api_dispatch_list', kwargs=dict(domain=wrong_domain.name,
                                                                       api_name=self.api_name,
                                                                       resource_name=self.resource.Meta.resource_name))
        response = self.client.post(wrong_list_endpoint, {'username': self.username, 'password': self.password})
        self.assertEqual(response.status_code, 403)
        wrong_domain.delete() 

    def test_wrong_credentials(self):
        '''
        If incorrect password for the correct username and domain pair are submitted, the response is forbidden
        '''
        response = self.client.post(self.list_endpoint, {'username': self.username, 'password': 'bimbizzleboozle'})
        self.assertEqual(response.status_code, 403)

    def test_no_username(self):
        '''
        If no username supplied, 400
        '''
        response = self.client.post(self.list_endpoint, {'password': 'bimbizzleboozle'})
        self.assertEqual(response.status_code, 400)

    def test_no_password(self):
        '''
        If no password supplied, 400
        '''
        response = self.client.post(self.list_endpoint, {'username': self.username})
        self.assertEqual(response.status_code, 400)

class TestGroupResource(APIResourceTest):

    resource = v0_5.GroupResource
    api_name = 'v0.5'

    def test_get_list(self):
        self.client.login(username=self.username, password=self.password)

        group = Group({"name": "test", "domain": self.domain.name})
        group.save()
        backend_id = group.get_id

        response = self.client.get(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_groups = simplejson.loads(response.content)['objects']
        self.assertEqual(len(api_groups), 1)
        self.assertEqual(api_groups[0]['id'], backend_id)

        group.delete()

    def test_get_single(self):
        self.client.login(username=self.username, password=self.password)

        group = Group({"name": "test", "domain": self.domain.name})
        group.save()
        backend_id = group.get_id

        response = self.client.get(self.single_endpoint(backend_id))
        self.assertEqual(response.status_code, 200)

        api_groups = simplejson.loads(response.content)
        self.assertEqual(api_groups['id'], backend_id)

    def test_create(self):
        self.client.login(username=self.username, password=self.password)

        self.assertEqual(0, len(Group.by_domain(self.domain.name)))

        group_json = {
            "case_sharing": True,
            "metadata": {
                "localization": "Ghana"
            },
            "name": "test group",
            "reporting": True,
        }
        response = self.client.post(self.list_endpoint,
                                    simplejson.dumps(group_json),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 201)
        [group_back] = Group.by_domain(self.domain.name)
        self.assertEqual(group_back.name, "test group")
        self.assertTrue(group_back.reporting)
        self.assertTrue(group_back.case_sharing)
        self.assertEqual(group_back.metadata["localization"], "Ghana")
        group_back.delete()

    def test_update(self):
        self.client.login(username=self.username, password=self.password)

        group = Group({"name": "test", "domain": self.domain.name})
        group.save()

        group_json =  {
            "case_sharing": True,
            "metadata": {
                "localization": "Ghana"
            },
            "name": "test group",
            "reporting": True,
        }

        backend_id = group._id
        response = self.client.put(self.single_endpoint(backend_id),
                                   simplejson.dumps(group_json),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 204, response.content)
        self.assertEqual(1, len(Group.by_domain(self.domain.name)))
        modified = Group.get(backend_id)
        self.assertEqual(modified.name, "test group")
        self.assertTrue(modified.reporting)
        self.assertTrue(modified.case_sharing)
        self.assertEqual(modified.metadata["localization"], "Ghana")
        modified.delete()


class FakeUserES(object):
    def __init__(self):
        self.docs = []
        self.queries = []

    def add_doc(self, doc):
        self.docs.append(doc)

    def make_query(self, q=None, fields=None, domain=None, start_at=None, size=None):
        self.queries.append(q)
        start = int(start_at) if start_at else 0
        end = min(len(self.docs), start + int(size)) if size else None
        return self.docs[start:end]


class TestBulkUserAPI(APIResourceTest):
    resource = v0_5.BulkUserResource
    api_name = 'v0.5'

    def setUp(self):
        self.domain = Domain.get_or_create_with_name('qwerty', is_active=True)
        self.username = 'rudolph@qwerty.commcarehq.org'
        self.password = '***'
        self.admin_user = WebUser.create(self.domain.name, self.username, self.password)
        self.admin_user.set_role(self.domain.name, 'admin')
        self.admin_user.save()

        self.fake_user_es = FakeUserES()
        v0_5.MOCK_BULK_USER_ES = self.mock_es_wrapper
        self.make_users()

    def tearDown(self):
        self.admin_user.delete()
        self.domain.delete()
        v0_5.MOCK_BULK_USER_ES = None

    def make_users(self):
        users = [
            ('Robb', 'Stark'),
            ('Jon', 'Snow'),
            ('Brandon', 'Stark'),
            ('Eddard', 'Stark'),
            ('Catelyn', 'Stark'),
            ('Tyrion', 'Lannister'),
            ('Tywin', 'Lannister'),
            ('Jamie', 'Lannister'),
            ('Cersei', 'Lannister'),
        ]
        for first, last in users:
            username = '_'.join([first.lower(), last.lower()])
            email = username + '@qwerty.commcarehq.org'
            self.fake_user_es.add_doc({
                'id': 'lskdjflskjflaj',
                'email': email,
                'username': username,
                'first_name': first,
                'last_name': last,
                'phone_numbers': ['9042411080'],
            })

    def mock_es_wrapper(self, *args, **kwargs):
        return self.fake_user_es.make_query(**kwargs)

    @property
    def list_endpoint(self):
        return reverse(
            'api_dispatch_list',
            kwargs={
                'domain': self.domain.name,
                'api_name': self.api_name,
                'resource_name': self.resource.Meta.resource_name,
            }
        )

    def test_excluded_field(self):
        result = self.query(fields=['email', 'first_name', 'password'])
        self.assertEqual(result.status_code, 400)

    def query(self, **params):
        self.client.login(username=self.username, password=self.password)
        url = '%s?%s' % (self.list_endpoint, urlencode(params, doseq=True))
        return self.client.get(url)

    def test_paginate(self):
        limit = 3
        result = self.query(limit=limit)
        self.assertEqual(result.status_code, 200)
        users = simplejson.loads(result.content)['objects']
        self.assertEquals(len(users), limit)

        result = self.query(start_at=limit, limit=limit)
        self.assertEqual(result.status_code, 200)
        users = simplejson.loads(result.content)['objects']
        self.assertEquals(len(users), limit)

    def test_basic(self):
        response = self.query()
        self.assertEqual(response.status_code, 200)
