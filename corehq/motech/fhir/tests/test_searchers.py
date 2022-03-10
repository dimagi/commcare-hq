from unittest.mock import Mock

import attr
from nose.tools import assert_equal, assert_in, assert_true

from corehq.motech.auth import BasicAuthManager
from corehq.motech.requests import Requests

from ..searchers import (
    EachUniqueValue,
    GivenName,
    ParamHelper,
    PatientSearcher,
    Search,
    SearchParam,
)


def test_param_helper():
    search_param = SearchParam('family', '$.name[*].family', ParamHelper)
    for resource, expected_valueset in [
        (
            {'name': [{'given': ['Jane'], 'family': 'Fonda'}]},
            'Fonda',
        ),
        (
            {'name': [
                {'given': ['Jane'], 'family': 'Fonda'},
                {'given': ['Jane'], 'family': 'Plemiannikov'},
            ]},
            {'Fonda', 'Plemiannikov'},
        ),
    ]:
        yield check_param_helper, search_param, resource, expected_valueset


def test_given_name():
    search_param = SearchParam('given', '$.name[0].given', GivenName)
    for resource, expected_valueset in [
        (
            {'name': [{'given': ['Jane'], 'family': 'Fonda'}]},
            'Jane',
        ),
        (
            {'name': [{'given': ['Jane', 'Seymour'], 'family': 'Fonda'}]},
            'Jane Seymour',
        ),
        (
            {'name': [{'family': 'Fonda'}]},
            None,
        ),
    ]:
        yield check_param_helper, search_param, resource, expected_valueset


def test_each_unique_value_given_names():
    search_param = SearchParam('given', '$.name[*].given', EachUniqueValue)
    for resource, expected_valueset in [
        (
            {'name': [{'given': ['Jane'], 'family': 'Fonda'}]},
            'Jane',
        ),
        (
            {'name': [{'given': ['Jane', 'Seymour'], 'family': 'Fonda'}]},
            {'Jane', 'Seymour'},
        ),
        (
            {'name': [{'family': 'Fonda'}]},
            None,
        ),
        (
            {'name': [
                {'given': ['Jane'], 'family': 'Fonda'},
                {'given': ['Jane'], 'family': 'Plemiannikov'},
            ]},
            'Jane',
        ),
        (
            {'name': [
                {'given': ['Jane', 'Seymour'], 'family': 'Fonda'},
                {'given': ['Jane', 'Seymour'], 'family': 'Plemiannikov'},
            ]},
            {'Jane', 'Seymour'},
        ),
        (
            {'name': [
                {'given': ['Jane', 'Seymour'], 'family': 'Fonda'},
                {'given': ['Jane', 'S.'], 'family': 'Plemiannikov'},
            ]},
            {'Jane', 'S.', 'Seymour'},
        ),
        (
            {'name': [
                {'family': 'Fonda'},
                {'family': 'Plemiannikov'},
            ]},
            None,
        ),
    ]:
        yield check_param_helper, search_param, resource, expected_valueset


def test_each_unique_value_countries():
    search_param = SearchParam('country', '$.address[*].country',
                               EachUniqueValue)
    for resource, expected_valueset in [
        (
            {'address': [{'country': 'USA'}]},
            'USA',
        ),
        (
            {'address': [
                {'country': 'USA'},
                {'country': 'France'},
            ]},
            {'USA', 'France'},
        ),
        (
            {'address': [
                {'state': 'New York'},
                {'state': 'Île-de-France'},
            ]},
            None,
        ),
        (
            {'address': [
                {'state': 'New York'},
                {'country': 'France'},
            ]},
            'France',
        ),
    ]:
        yield check_param_helper, search_param, resource, expected_valueset


def test_each_unique_value_phones():
    search_param = SearchParam('phone', "$.telecom[?system='phone'].value",
                               EachUniqueValue)
    for resource, expected_valueset in [
        (
            {'telecom': [{'system': 'phone', 'value': '(555) 675 5745'}]},
            '(555) 675 5745',
        ),
        (
            {'telecom': [
                {'system': 'phone', 'value': '+1 555 675 5745'},
                {'system': 'phone', 'value': '(555) 675 5745'},
            ]},
            {'+1 555 675 5745', '(555) 675 5745'},
        ),
        (
            {'telecom': [
                {'system': 'email', 'value': 'user@example.com'},
                {'system': 'email', 'value': 'admin@example.com'},
            ]},
            None,
        ),
        (
            {'telecom': [
                {'system': 'phone', 'value': '+1 555 675 5745'},
                {'system': 'email', 'value': 'user@example.com'},
            ]},
            '+1 555 675 5745',
        ),
    ]:
        yield check_param_helper, search_param, resource, expected_valueset


def check_param_helper(search_param, resource, expected_valueset):
    value = search_param.param.get_value(resource)
    if isinstance(value, list):
        value = set(value)
    assert_equal(value, expected_valueset)


def test_get_request_params_multiplies():
    # Broad searches by names:
    #     '$.name[*].given'
    #     '$.name[*].family'
    search_params = PatientSearcher.search_search_params[2]
    resource = {
        'name': [
            {'given': ['Jane', 'Seymour'], 'family': 'Fonda'},
            {'given': ['Jane', 'Seymour'], 'family': 'Plemiannikov'},
        ]
    }
    search = Search(None, resource, search_params)
    request_params = search._get_request_params()
    assert_equal(len(request_params), 4)
    assert_in({'given': 'Jane', 'family': 'Fonda'}, request_params)
    assert_in({'given': 'Seymour', 'family': 'Fonda'}, request_params)
    assert_in({'given': 'Jane', 'family': 'Plemiannikov'}, request_params)
    assert_in({'given': 'Seymour', 'family': 'Plemiannikov'}, request_params)


def test_get_request_params_incomplete_data():
    # Personal details:
    #     '$.name[0].given'
    #     '$.name[0].family'
    #     '$.gender'
    #     '$.birthDate'
    #     "$.telecom[?system='email'].value"
    #     "$.telecom[?system='phone'].value"
    #     '$.address[*].country'
    #     '$.address[*].state'
    #     '$.address[*].city'
    search_params = PatientSearcher.search_search_params[1]
    resource = {
        'name': [{'given': ['Jane', 'Seymour'], 'family': 'Fonda'}],
        'gender': 'female',
        'birthDate': '1937-12-21',
        'address': [{'country': 'United States of America'}],
    }
    search = Search(None, resource, search_params)
    request_params = search._get_request_params()
    assert_equal(len(request_params), 1)
    assert_equal(request_params[0], {
        'given': 'Jane Seymour',
        'family': 'Fonda',
        'gender': 'female',
        'birthdate': '1937-12-21',
        'address-country': 'United States of America',
    })


def test_paginated_bundle():

    @attr.s(auto_attribs=True)
    class Response:
        data: dict

        def json(self):
            return self.data

    fane_jonda = {
        'resourceType': 'Patient',
        'name': [{'given': ['Fane'], 'family': 'Jonda'}],
    }
    jone_fanda = {
        'resourceType': 'Patient',
        'name': [{'given': ['Jone'], 'family': 'Fanda'}],
    }
    jane_fonda = {
        'resourceType': 'Patient',
        'name': [{'given': ['Jane'], 'family': 'Fonda'}],
    }

    base_url = 'https://example.com/api/'
    requests = Requests('test-domain', base_url,
                        auth_manager=BasicAuthManager('user', 'pass'))
    # First requests.get should be called with a search endpoint
    requests.get = Mock(return_value=Response({
        'resourceType': 'bundle',
        'link': [
            {'relation': 'self', 'url': base_url + 'Patient/page/1'},  # Page 1
            {'relation': 'next', 'url': base_url + 'Patient/page/2'},
        ],
        'entry': [
            {'resource': fane_jonda},
            {'resource': jone_fanda},
        ],
    }))
    # requests.send_request should be called with urls for subsequent pages
    requests.send_request = Mock(return_value=Response({
        'resourceType': 'bundle',
        'link': [
            {'relation': 'self', 'url': base_url + 'Patient/page/2'},  # Page 2
            {'relation': 'previous', 'url': base_url + 'Patient/page/1'},
        ],
        'entry': [{'resource': jane_fonda}],
    }))

    resource = {
        'resourceType': 'Patient',
        'name': [{'given': ['Jane', 'Seymour'], 'family': 'Fonda'}],
        'gender': 'female',
        'birthDate': '1937-12-21',
        'address': [{'country': 'United States of America'}],
    }
    search_params = PatientSearcher.search_search_params[1]
    search = Search(requests, resource, search_params)
    candidates = search.iter_candidates()

    assert_equal(next(candidates), fane_jonda)
    assert_equal(next(candidates), jone_fanda)
    assert_equal(next(candidates), jane_fonda)

    # The first request searched the Patient endpoint
    assert_true(requests.get.called_with('Patient/', params={
        'given': 'Jane Seymour',
        'family': 'Fonda',
        'gender': 'female',
        'birthdate': '1937-12-21',
        'address-country': 'United States of America',
    }))

    # The next request called the "next" URL
    assert_true(requests.get.called_with(
        'GET',
        'https://example.com/api/Patient/page/2',
    ))
