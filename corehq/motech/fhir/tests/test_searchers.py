from nose.tools import assert_equal, assert_in

from ..searchers import (
    EachUniqueValue,
    GivenName,
    ParamHelper,
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
    search_params = [
        SearchParam('given', '$.name[*].given', EachUniqueValue),
        SearchParam('family', '$.name[*].family'),
    ]
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


# TODO: test bundle pagination
