import pytest
from tastypie.constants import ALL

from corehq.apps.api.openapi.catalogue import ApiEntry, USER
from corehq.apps.api.openapi.operations import (
    filter_parameters,
    resource_paths,
    standard_list_parameters,
)
from corehq.apps.api.resources import v0_5


def names(parameters):
    return [p['name'] for p in parameters]


def test_exact_filter_gives_a_bare_parameter():
    params = filter_parameters({'domain': ('exact',)})
    assert names(params) == ['domain']
    assert params[0]['in'] == 'query'
    assert params[0]['required'] is False


def test_comparison_filters_are_suffixed():
    params = filter_parameters({'date': ('exact', 'gt', 'lte')})
    assert names(params) == ['date', 'date__gt', 'date__lte']


def test_all_constant_gives_a_bare_parameter():
    assert names(filter_parameters({'name': ALL})) == ['name']


def test_filters_are_sorted_for_stable_output():
    params = filter_parameters({'b': ('exact',), 'a': ('exact',)})
    assert names(params) == ['a', 'b']


def test_standard_list_parameters():
    params = standard_list_parameters({'default_limit': 20})
    assert names(params) == ['limit', 'offset', 'format']
    limit = params[0]
    assert limit['schema']['default'] == 20
    assert limit['schema']['type'] == 'integer'


def test_order_by_is_added_when_the_resource_declares_ordering():
    params = standard_list_parameters(
        {'default_limit': 20, 'ordering': ['date_modified']}
    )
    assert names(params) == ['limit', 'offset', 'format', 'order_by']
    order_by = params[-1]
    assert order_by['schema']['enum'] == [
        'date_modified',
        '-date_modified',
    ]


def test_domain_resource_paths():
    """v0_5.CommCareUserResource allows GET/POST on the list and
    GET/PUT/DELETE on the detail endpoint."""
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    paths = resource_paths(entry)
    assert set(paths) == {
        '/a/{domain}/api/user/v1/',
        '/a/{domain}/api/user/v1/{pk}/',
    }
    assert set(paths['/a/{domain}/api/user/v1/']) == {
        'get',
        'post',
        'parameters',
    }
    assert set(paths['/a/{domain}/api/user/v1/{pk}/']) == {
        'get',
        'put',
        'delete',
        'parameters',
    }


def test_list_endpoint_with_no_detail_methods_omits_the_detail_path():
    entry = ApiEntry(v0_5.IdentityResource, 'v1', 'identity-v1', scope=USER)
    paths = resource_paths(entry)
    assert set(paths) == {'/api/identity/v1/'}


def test_domain_is_a_required_path_parameter():
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    paths = resource_paths(entry)
    path_params = paths['/a/{domain}/api/user/v1/']['parameters']
    domain = next(p for p in path_params if p['name'] == 'domain')
    assert domain['in'] == 'path'
    assert domain['required'] is True


def test_user_scoped_paths_have_no_domain():
    entry = ApiEntry(v0_5.IdentityResource, 'v1', 'identity-v1', scope=USER)
    paths = resource_paths(entry)
    assert all(not p.startswith('/a/') for p in paths)
    assert '/api/identity/v1/' in paths


def test_operation_lists_the_required_permission():
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    operation = resource_paths(entry)['/a/{domain}/api/user/v1/']['get']
    assert 'edit_commcare_users' in operation['description']


def test_write_methods_carry_a_request_body_of_writable_fields():
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    paths = resource_paths(entry)
    post = paths['/a/{domain}/api/user/v1/']['post']
    schema = post['requestBody']['content']['application/json']['schema']
    assert schema['type'] == 'object'
    assert 'username' in schema['properties']
    assert 'id' not in schema['properties'], (
        'read-only fields must not appear in request bodies'
    )


def test_read_methods_have_no_request_body():
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    get = resource_paths(entry)['/a/{domain}/api/user/v1/']['get']
    assert 'requestBody' not in get


def test_delete_has_no_request_body():
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    paths = resource_paths(entry)
    delete = paths['/a/{domain}/api/user/v1/{pk}/']['delete']
    assert 'requestBody' not in delete


@pytest.mark.parametrize(
    'resource_cls, version',
    [
        (v0_5.GroupResource, 'v1'),
        (v0_5.WebUserResource, 'v1'),
        (v0_5.BulkUserResource, 'v1'),
    ],
)
def test_paths_generate_without_error_for_other_resources(
    resource_cls, version
):
    paths = resource_paths(ApiEntry(resource_cls, version, 'slug'))
    assert paths
