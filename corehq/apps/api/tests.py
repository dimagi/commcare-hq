import simplejson
from datetime import datetime

from django.utils.http import urlencode
from django.test import TestCase
from django.core.urlresolvers import reverse

from couchforms.models import XFormInstance

from corehq.pillows.xform import XFormPillow
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.domain.models import Domain
from corehq.apps.receiverwrapper.models import FormRepeater, CaseRepeater, ShortFormRepeater
from corehq.apps.api.resources import v0_1, v0_4

class FakeXFormES(object):
    """
    A mock of XFormES that will return the docs that have been
    added regardless of the query.
    """
    
    def __init__(self):
        self.docs = []

    def add_doc(self, id, doc):
        self.docs.append(doc)
    
    def run_query(self, query):
        return {
            'hits': {
                'total': len(self.docs),
                'hits': [{'_source': doc} for doc in self.docs]
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
        self.list_endpoint = reverse('api_dispatch_list', kwargs=dict(domain=self.domain.name,
                                                                      api_name=self.api_name,
                                                                      resource_name=self.resource.Meta.resource_name))
        self.username = 'rudolph'
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


class TestCommCareUserResource(APIResourceTest):
    """
    Basic sanity checking of v0_1.CommCareUserResource
    """
    resource = v0_1.CommCareUserResource
        
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


class TestWebUserResource(APIResourceTest):
    """
    Basic sanity checking of v0_1.CommCareUserResource
    """
    resource = v0_1.WebUserResource

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
