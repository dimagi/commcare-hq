import random
import string
from collections import namedtuple
from datetime import datetime, timedelta
from unittest import SkipTest
from uuid import uuid4

from django.conf import settings
from django.test import TestCase

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.models import ConnectionSettings

from ..models import FHIRResourceProperty, FHIRResourceType
from ..repeaters import FHIRRepeater

DOMAIN = ''.join([random.choice(string.ascii_lowercase) for __ in range(20)])
CASE_ID = str(uuid4())
INSTANCE_ID = str(uuid4())

# This test was run with a SMART-on-FHIR HAPI FHIR Docker image:
#     $ docker run -it -p 8425:8080 smartonfhir/hapi-5:r4-synthea
# See https://hub.docker.com/u/smartonfhir/
BASE_URL = 'http://localhost:8425/hapi-fhir-jpaserver/fhir/'


ResponseMock = namedtuple('ResponseMock', 'status_code reason')


class TestPatientRegistration(TestCase, DomainSubscriptionMixin):
    """
    Submits an XForm, and tracks progress to a FHIR server.

    Requires Celery to be running for ``process_repeat_record()`` task.
    """

    def __new__(cls, *args, **kwargs):
        # @skip still executes tearDownClass() (?!) This does not:
        raise SkipTest('Requires local HAPI FHIR instance')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.set_up_domain()
        cls.set_up_case_type()
        cls.set_up_repeater()

        cls._debug = settings.DEBUG
        settings.DEBUG = True  # urlsanitize to allow localhost URLs
        post_xform()

    @classmethod
    def set_up_domain(cls):
        cls.domain_obj = create_domain(DOMAIN)
        cls.setup_subscription(DOMAIN, SoftwarePlanEdition.PRO)

    @classmethod
    def set_up_case_type(cls):
        case_type = CaseType.objects.create(domain=DOMAIN, name='mother')
        resource_type = FHIRResourceType.objects.create(
            domain=DOMAIN,
            case_type=case_type,
            name='Patient',
        )
        for name, jsonpath in [
            ('name', '$.name[0].text'),
            ('first_name', '$.name[0].given[0]'),
            ('honorific', '$.name[0].prefix[0]'),
            ('date_of_birth', '$.birthDate'),
        ]:
            prop = CaseProperty.objects.create(case_type=case_type, name=name)
            FHIRResourceProperty.objects.create(
                resource_type=resource_type,
                case_property=prop,
                jsonpath=jsonpath,
            )

    @classmethod
    def set_up_repeater(cls):
        cls.conn = ConnectionSettings.objects.create(
            domain=DOMAIN,
            name='Fhirplace',
            url=BASE_URL,
        )
        cls.repeater = FHIRRepeater(
            domain=DOMAIN,
            connection_settings_id=cls.conn.id,
        )
        cls.repeater.save()

    @classmethod
    def tearDownClass(cls):
        cls.tear_down_fhir_patient()

        settings.DEBUG = cls._debug
        cls.repeater.delete()
        cls.conn.delete()

        CaseType.objects.filter(domain=DOMAIN, name='mother').delete()

        cls.teardown_subscriptions()
        cls.domain_obj.delete()
        clear_plan_version_cache()
        super().tearDownClass()

    @classmethod
    def tear_down_fhir_patient(cls):
        requests = cls.conn.get_requests()
        search_response = requests.get('Patient?given=Plethwih')
        searchset_bundle = search_response.json()
        for entry in searchset_bundle.get('entry', []):
            # This DELETE request adheres to [the FHIR API standard](
            # http://hl7.org/implement/standards/fhir/http.html#delete)
            # but fails:
            # ca.uhn.fhir.rest.server.exceptions.InvalidRequestException:
            # URL path has unexpected token '219155' at the end:
            # http://localhost:8080/hapi-fhir-jpaserver/fhir/Patient/219155
            requests.delete(entry['fullUrl'])

    def test_external_id(self):
        case = CaseAccessors(DOMAIN).get_case(CASE_ID)
        self.assertTrue(bool(case.external_id))

    def test_remote_search(self):
        requests = self.conn.get_requests()
        search_response = requests.get('Patient?given=Plethwih')
        searchset_bundle = search_response.json()
        self.assertGreater(searchset_bundle['total'], 0)


def post_xform():

    def isoformat(dt):
        return dt.isoformat(timespec='milliseconds') + 'Z'

    user_id = str(uuid4())
    just_now = datetime.utcnow()
    time_start = isoformat(just_now - timedelta(minutes=2))
    time_end = isoformat(just_now - timedelta(minutes=1))
    date_modified = isoformat(just_now)

    xform = f"""<?xml version='1.0' ?>
<data xmlns="https://www.commcarehq.org/test/TestPatientRegistration/">
  <honorific>Mehter</honorific>
  <first_name>Plethwih</first_name>
  <name>Mehter Plethwih</name>
  <date_of_birth>1970-01-01</date_of_birth>

  <tx:case case_id="{CASE_ID}"
           date_modified="{date_modified}"
           user_id="{user_id}"
           xmlns:tx="http://commcarehq.org/case/transaction/v2">
    <tx:create>
      <tx:case_name>Mehter Plethwih</tx:case_name>
      <tx:owner_id>{user_id}</tx:owner_id>
      <tx:case_type>mother</tx:case_type>
    </tx:create>
    <tx:update>
      <tx:honorific>Mehter</tx:honorific>
      <tx:first_name>Plethwih</tx:first_name>
      <tx:date_of_birth>1970-01-01</tx:date_of_birth>
    </tx:update>
  </tx:case>

  <jr:meta xmlns:jr="http://dev.commcarehq.org/jr/xforms">
    <jr:deviceID>TestPatientRegistration</jr:deviceID>
    <jr:timeStart>{time_start}</jr:timeStart>
    <jr:timeEnd>{time_end}</jr:timeEnd>
    <jr:username>admin</jr:username>
    <jr:userID>testy.mctestface</jr:userID>
    <jr:instanceID>{INSTANCE_ID}</jr:instanceID>
  </jr:meta>
</data>
"""
    submit_form_locally(xform, DOMAIN)
