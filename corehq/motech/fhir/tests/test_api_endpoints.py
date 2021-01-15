"""
These tests set goals for the functionality of CommCare's FHIR API.

Examples are based on HAPI FHIR. You can explore requests and responses
using their `online test server`_.


.. _online test server: https://hapi.fhir.org/resource?serverId=home_r4&pretty=false&_summary=&resource=Patient#

"""
from unittest import skip
from uuid import uuid4

from django.test import TestCase

import requests

from casexml.apps.case.mock import CaseBlock

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.tzmigration.timezonemigration import json_diff
from corehq.apps.users.models import WebUser
from corehq.motech.utils import get_endpoint_url

DOMAIN = 'fhir-drill'
FHIR_VERSION = 'R4'  # We do not need to support older versions (e.g. DSTU2)
# MVP: API is domain-specific, like existing API.
BASE_URL = f'localhost:8080/a/{DOMAIN}/api/fhir/{FHIR_VERSION}/'
API_USERNAME = f'admin@{DOMAIN}.commcarehq.org'
API_PASSWORD = 'Passw0rd!'
FOO_CASE_ID = uuid4().hex
BAR_CASE_ID = uuid4().hex
BAZ_CASE_ID = uuid4().hex


@skip('Covered functionality not yet implemented')
class PatientEndpointTests(TestCase, DomainSubscriptionMixin):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        # Assumes FHIR API needs Pro plan
        cls.setup_subscription(DOMAIN, SoftwarePlanEdition.PRO)
        cls.user = WebUser.create(DOMAIN, API_USERNAME, API_PASSWORD,
                                  created_by=None, created_via=None)
        create_person_cases(owner_id=cls.user.user_id)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(deleted_by=None)
        cls.teardown_subscriptions()
        cls.domain_obj.delete()
        clear_plan_version_cache()
        super().tearDownClass()

    def test_search(self):
        # Tests filtering by a non-indexed case property
        url = get_endpoint_url(BASE_URL, '/Patient?birthdate=1990-01-01')
        response = requests.get(url, auth=(API_USERNAME, API_PASSWORD))

        # Some things will be different between the expected search
        # result and the actual response. Use `json_diff()` to confirm
        # expected differences, and that everything else is the same.
        diffs = sorted([diff.path for diff in json_diff(response.json(),
                                                        get_search_result())])
        self.assertEqual(diffs, ['id', 'meta.lastUpdated'])

    def test_get(self):
        url = get_endpoint_url(BASE_URL, f'/Patient/{FOO_CASE_ID}')
        response = requests.get(url, auth=(API_USERNAME, API_PASSWORD))
        self.assertEqual(response.json(), FOO_PATIENT)

    def test_auth_bad_password(self):
        # Authentication should use the same code as existing API
        url = get_endpoint_url(BASE_URL, f'/Patient/{FOO_CASE_ID}')
        with self.assertRaisesRegex(requests.HTTPError, '[Ff]orbidden'):
            requests.get(url, auth=(API_USERNAME, 'bad_password'))

    def test_auth_bad_username(self):
        url = get_endpoint_url(BASE_URL, f'/Patient/{FOO_CASE_ID}')
        with self.assertRaisesRegex(requests.HTTPError, '[Ff]orbidden'):
            # Error should be the same as for bad password: It should
            # not reveal that the user does not exist.
            requests.get(url, auth=('admin@example.com', API_PASSWORD))

    def test_auth_bad_resource(self):
        url = get_endpoint_url(BASE_URL, f'/Patient/{BAZ_CASE_ID}')
        with self.assertRaisesRegex(requests.HTTPError, '[Nn]ot found'):
            requests.get(url, auth=(API_USERNAME, API_PASSWORD))


def create_person_cases(owner_id):
    """
    Creates cases for Fred Foo and Barbara Bar.
    """
    different_owner_id = uuid4().hex
    submit_case_blocks([
        get_foo_caseblock(owner_id).as_text(),
        get_bar_caseblock(owner_id).as_text(),
        get_baz_caseblock(different_owner_id).as_text(),
    ], DOMAIN)


def get_search_result():
    bundle_id = str(uuid4())
    return {
        "resourceType": "Bundle",
        "id": bundle_id,
        "meta": {
            "lastUpdated": "2021-01-14T07:54:36.100+00:00"
        },
        "type": "searchset",
        "total": 2,
        "link": [
            {
                "relation": "self",
                "url": get_endpoint_url(BASE_URL, '/Patient?birthdate=1990-01-01'),
            },
            # Keeping this here for reference. This is how pagination
            # works by default in HAPI FHIR. We can use any GET params
            # way we want, as long as the URL we provide here will
            # return a Bundle with the next page of search results.
            # {
            #     "relation": "next",
            #     "url": f'{BASE_URL}?'
            #            f"_getpages={bundle_id}"
            #            "&_getpagesoffset=20"
            #            "&_count=20"
            #            "&_bundletype=searchset"
            # }
        ],
        "entry": [
            {
                "fullUrl": get_endpoint_url(BASE_URL, f'/Patient/{FOO_CASE_ID}'),
                "resource": FOO_PATIENT,
                "search": {
                    "mode": "match"
                }
            }, {
                "fullUrl": get_endpoint_url(BASE_URL, f'/Patient/{BAR_CASE_ID}'),
                "resource": BAR_PATIENT,
                "search": {
                    "mode": "match"
                }
            }
        ]
    }


def get_foo_caseblock(owner_id):
    return CaseBlock(
        create=True,
        case_id=FOO_CASE_ID,
        case_type='person',
        case_name='FOO, Fred',
        external_id='PM-ZAF-F01234567',
        owner_id=owner_id,
        update={
            'first_name': 'Fred',
            'last_name': 'Foo',
            'passport_type': 'PM',
            'passport_country_code': 'ZAF',
            'passport_number': 'F01234567',
            'sex': 'male',
            'dob': '1990-01-01',
            'covid19_last_test_date': '2021-01-01',
            'covid19_last_test_status': 'negative',
        }
    )


FOO_PATIENT = {
    "resourceType": "Patient",
    "id": FOO_CASE_ID,
    # We could get `lastUpdated` from the case.
    # TODO: It's not a user-defined case property. How would we map it?
    #       Or do we just include it in all resources?
    # "meta": {
    #     "lastUpdated": "2020-12-08T02:37:47.219+00:00",
    # },
    "identifier": [{
        # We can't do this with a mapping. I think we're going to need
        # to allow users to set a JSON template for each case type, and
        # then we use [JSONPath](https://github.com/h2non/jsonpath-ng)
        # to modify / extend it.
        "type": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                # [Passport Number](https://terminology.hl7.org/2.0.0/CodeSystem-v2-0203.html)
                "code": "PPN"
            }]
        },
        # Data Dictionary: 'passport_number' -> 'identifier[0].value'
        "value": "F01234567",
        "assigner": {
            # Data Dictionary: 'passport_number' -> 'identifier[0].assigner.display'
            # We could use a mapping to map country codes to country
            # names, but not with the Data Dictionary UI.
            "display": "ZAF"
        }
    }],
    # I don't know if `active` is required. If so, we can just use the
    # template mentioned above to set `"active": True` for all cases. If
    # it's not required, we should leave this out.
    "active": True,
    "name": [{
        # Data Dictionary: 'last_name' -> 'name[0].family'
        "family": "Foo",
        # Data Dictionary: 'first_name' -> 'name[0].given[0]'
        "given": ["Fred"]  # Note: List
    }],
    # Data Dictionary: 'sex' -> 'gender'
    "gender": "male",
    # Data Dictionary: 'dob' -> 'birthDate'
    "birthDate": "1990-01-01",
}


def get_bar_caseblock(owner_id):
    return CaseBlock(
        create=True,
        case_id=BAR_CASE_ID,
        case_type='person',
        case_name='BAR, Barbara',
        external_id='PM-ZAF-B01234567',
        owner_id=owner_id,
        update={
            'first_name': 'Barbara',
            'last_name': 'Bar',
            'passport_type': 'PM',
            'passport_country_code': 'ZAF',
            'passport_number': 'B01234567',
            'sex': 'female',
            'dob': '1990-01-01',
            'covid19_last_test_date': '2021-01-01',
            'covid19_last_test_status': 'negative',
        }
    )


BAR_PATIENT = {
    "resourceType": "Patient",
    "id": BAR_CASE_ID,
    "identifier": [{
        "type": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                "code": "PPN"
            }]
        },
        "value": "B01234567",
        "assigner": {
            "display": "ZAF"
        }
    }],
    "active": True,
    "name": [{
        "family": "Bar",
        "given": ["Barbara"]
    }],
    "gender": "female",
    "birthDate": "1990-01-01",
}


def get_baz_caseblock(owner_id):
    return CaseBlock(
        create=True,
        case_id=BAZ_CASE_ID,
        case_type='person',
        case_name='BAZ, Bazza',
        external_id='P-GBR-012345678',
        owner_id=owner_id,
        update={
            'first_name': 'Bazza',
            'last_name': 'Baz',
            'passport_type': 'P',
            'passport_country_code': 'GBR',
            'passport_number': '012345678',
            'sex': 'male',
            'dob': '1990-01-01',
            'covid19_last_test_date': '2021-01-01',
            'covid19_last_test_status': 'negative',
        }
    )
