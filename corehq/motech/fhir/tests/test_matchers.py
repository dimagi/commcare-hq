from nose.tools import assert_equal

from ..matchers import PersonMatcher, OrganizationMatcher


def test_given_name_method():
    # Tests the GivenName ComparisonMethod as used by PersonMatcher
    pw = PersonMatcher.property_weights[0]
    method = pw.method
    assert method.__class__.__name__ == 'GivenName'

    john = {'name': [{'given': 'Henry John Colchester'.split(' ')}]}
    for resource, candidate, expected in [
        (john, {'name': [{'given': ['H.', 'John']}]}, True),
        (john, {'name': [{'given': ['H.', 'J.', 'C.']}]}, False),
        (john, {'name': [{'given': ['Henry']}]}, True),
        (john, {'name': [{'given': ['John']}]}, False),
    ]:
        yield check_method, method, resource, candidate, expected


def test_organization_name_method():
    # Tests the OrganizationName method as used by OrganizationMatcher
    pw = OrganizationMatcher.property_weights[0]
    method = pw.method
    assert method.__class__.__name__ == 'OrganizationName'

    dimagi = {'name': 'Dimagi'}
    for resource, candidate, expected in [
        (dimagi, {'name': 'Dimagi'}, True),
        (dimagi, {'name': 'DiMaggi'}, True),
        (dimagi, {'name': 'Di Maggi'}, False),
    ]:
        yield check_method, method, resource, candidate, expected


def check_method(method, a, b, expected):
    result = method.is_match(a, b)
    assert_equal(result, expected)
