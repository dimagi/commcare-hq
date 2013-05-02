import simplejson
from datetime import datetime

from django.utils.http import urlencode
from django.test import TestCase
from django.core.urlresolvers import reverse

from couchforms.models import XFormInstance

from corehq.pillows.xform import XFormPillow
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.domain.models import Domain
from corehq.apps.api.resources import v0_4

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


class TestXFormInstanceResource(TestCase):
    """
    Tests the XFormInstanceResource, currently only v0_4

    TODO: Provide tests for each version, especially for those aspects
    which differ between versions. They should call into reusable tests
    for the functionality that is not different.
    """
    
    def setUp(self):
        self.maxDiff = None
        
        self.domain = Domain.get_or_create_with_name('qwerty', is_active=True)

        self.list_endpoint = reverse('api_dispatch_list', kwargs=dict(domain=self.domain.name, 
                                                                      api_name='v0.4', 
                                                                      resource_name=v0_4.XFormInstanceResource.Meta.resource_name))
        

        self.username = 'rudolph'
        self.password = '***'
        self.user = WebUser.create(self.domain.name, self.username, self.password)
        self.user.set_role(self.domain.name, 'admin')
        self.user.save()

    def tearDown(self):
        self.user.delete()
        self.domain.delete()

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
