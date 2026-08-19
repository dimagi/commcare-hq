import pytest
from tastypie.constants import ALL

from corehq.apps.api.openapi.catalogue import (
    ApiEntry,
    USER,
    documented_entries,
)
from corehq.apps.api.openapi.declarations import RESOURCE_URI_DESCRIPTION
from corehq.apps.api.openapi.docs import collect_docs, reject_misfiled_docs
from corehq.apps.api.openapi.operations import (
    filter_parameters,
    object_schema,
    resource_paths,
    standard_list_parameters,
)
from corehq.apps.api.resources import v0_5
from corehq.apps.fixtures.resources import v0_1 as fixtures_v0_1
from corehq.apps.locations.resources import v0_6


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
    params = standard_list_parameters({'default_limit': 20}, 1000)
    assert names(params) == ['limit', 'offset', 'format']
    limit = params[0]
    assert limit['schema']['default'] == 20
    assert limit['schema']['type'] == 'integer'
    assert limit['description'] == (
        'Maximum number of records to return, capped at 1000. '
        'Use 0 to request that maximum.'
    )


def test_limit_says_zero_means_everything_only_without_a_cap():
    """Paginator.get_limit() returns max_limit when limit is 0, so
    "0 means all records" is true only for an uncapped resource."""
    capped = standard_list_parameters({'default_limit': 20}, 5000)[0]
    assert 'capped at 5000' in capped['description']
    assert 'all records' not in capped['description']
    uncapped = standard_list_parameters({'default_limit': 20}, None)[0]
    assert uncapped['description'] == (
        'Maximum number of records to return. '
        'Use 0 to request all records.'
    )


def test_order_by_is_added_when_the_resource_declares_ordering():
    params = standard_list_parameters(
        {'default_limit': 20, 'ordering': ['date_modified']}, 1000
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
        '/a/{domain}/api/user/v1/{pk}/activate/',
        '/a/{domain}/api/user/v1/{pk}/deactivate/',
        '/a/{domain}/api/user/v1/{pk}/email_password_reset/',
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


def test_an_added_field_becomes_a_property_in_its_own_right():
    resource_schema = {'fields': {'name': {'type': 'string'}}}
    docs = {
        'added_fields': {
            'extra_field': {
                'type': 'string',
                'description': 'A field the resource adds outside of '
                              'Tastypie field machinery.',
            },
        },
    }
    schema = object_schema(resource_schema, docs)
    assert schema['properties']['extra_field'] == {
        'type': 'string',
        'description': 'A field the resource adds outside of Tastypie '
                       'field machinery.',
    }
    # A declared field with no override is unaffected.
    assert schema['properties']['name'] == {'type': 'string'}


def test_resource_uri_is_described_without_the_resource_declaring_it():
    """The description is boilerplate every resource means the same way,
    so it is applied centrally rather than declared nine times."""
    resource_schema = {
        'fields': {'resource_uri': {'type': 'string', 'readonly': True}}
    }
    schema = object_schema(resource_schema, {})
    assert schema['properties']['resource_uri'] == {
        'type': 'string',
        'readOnly': True,
        'description': RESOURCE_URI_DESCRIPTION,
    }


def test_a_resource_can_still_override_the_resource_uri_description():
    resource_schema = {'fields': {'resource_uri': {'type': 'string'}}}
    docs = {'field_schemas': {'resource_uri': {'description': 'Special.'}}}
    schema = object_schema(resource_schema, docs)
    assert schema['properties']['resource_uri']['description'] == 'Special.'


def test_field_schemas_entry_for_a_declared_field_still_overrides():
    resource_schema = {'fields': {'name': {'type': 'string'}}}
    docs = {'field_schemas': {'name': {'type': 'integer'}}}
    schema = object_schema(resource_schema, docs)
    assert schema['properties']['name'] == {'type': 'integer'}


def test_location_v2_response_schema_includes_its_ad_hoc_fields():
    """location v2's dehydrate() adds fields outside of Tastypie's field
    machinery; Docs.field_schemas documents them as additions, and they
    must show up in the generated response schema (not just the example),
    or the example and schema contradict each other."""
    entry = ApiEntry(v0_6.LocationResource, 'v2', 'location-v2')
    operation = resource_paths(entry)['/a/{domain}/api/location/v2/']['get']
    item_schema = operation['responses']['200']['content'][
        'application/json'
    ]['schema']['properties']['objects']['items']
    for name in (
        'parent_location_id',
        'location_type_name',
        'location_type_code',
    ):
        assert name in item_schema['properties'], (
            f'{name} is missing from the location-v2 response schema'
        )
        assert item_schema['properties'][name]['type'] == 'string'


def test_write_only_fields_are_flagged_but_still_writable():
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    paths = resource_paths(entry)

    get_item_schema = paths['/a/{domain}/api/user/v1/']['get'][
        'responses'
    ]['200']['content']['application/json']['schema']['properties'][
        'objects'
    ]['items']
    for name in (
        'require_account_confirmation',
        'send_confirmation_email_now',
    ):
        assert get_item_schema['properties'][name]['writeOnly'] is True

    request_body_schema = paths['/a/{domain}/api/user/v1/']['post'][
        'requestBody'
    ]['content']['application/json']['schema']
    assert 'require_account_confirmation' in request_body_schema[
        'properties'
    ]
    assert 'send_confirmation_email_now' in request_body_schema[
        'properties'
    ]
    assert 'id' not in request_body_schema['properties'], (
        'read-only fields must still be excluded from request bodies'
    )


def test_user_v1_request_body_excludes_fields_the_resource_rejects():
    """CommcareUserUpdates.update() rejects any key outside its own
    dispatch table; ``eulas`` (inherited from UserResource) is not in it,
    so publishing it as writable would advertise a field that gets a 400
    ('Attempted to update unknown or non-editable field') in practice."""
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    paths = resource_paths(entry)
    for path, method in (
        ('/a/{domain}/api/user/v1/', 'post'),
        ('/a/{domain}/api/user/v1/{pk}/', 'put'),
    ):
        schema = paths[path][method]['requestBody']['content'][
            'application/json'
        ]['schema']
        assert 'eulas' not in schema['properties']
        assert 'username' in schema['properties']
        assert 'password' in schema['properties']


def test_web_user_v1_request_body_is_restricted_to_genuinely_writable_fields():
    """WebUserUpdates.update() only dispatches role, location, user_data,
    tableau_role and tableau_groups; every other declared field --
    including username, email, first_name, last_name, phone_numbers,
    default_phone_number, eulas, is_admin, permissions and
    is_active_in_domain -- is either dehydrate-only or rejected outright,
    so it must not appear in the PATCH request body."""
    entry = ApiEntry(v0_5.WebUserResource, 'v1', 'web-user-v1')
    paths = resource_paths(entry)
    schema = paths['/a/{domain}/api/web-user/v1/{pk}/']['patch'][
        'requestBody'
    ]['content']['application/json']['schema']
    assert set(schema['properties']) == {
        'role',
        'primary_location_id',
        'assigned_location_ids',
        'profile',
        'user_data',
        'tableau_role',
        'tableau_groups',
    }


@pytest.mark.parametrize(
    'resource_cls, version, doc_slug, detail_path',
    [
        (
            v0_5.CommCareUserResource, 'v1', 'user-v1',
            '/a/{domain}/api/user/v1/{pk}/',
        ),
        (
            v0_6.LocationResource, 'v2', 'location-v2',
            '/a/{domain}/api/location/v2/{location_id}/',
        ),
    ],
)
def test_put_does_not_advertise_a_201_it_cannot_return(
    resource_cls, version, doc_slug, detail_path
):
    """user-v1's obj_update raises couch's ResourceNotFound (-> 500) and
    location-v2's raises LocationAPIError (-> 400) for a missing record;
    neither ever reaches tastypie's create-on-PUT fallback, so PUT must
    not document a 201 alternative."""
    entry = ApiEntry(resource_cls, version, doc_slug)
    put = resource_paths(entry)[detail_path]['put']
    assert set(put['responses']) - {'201'} == set(put['responses']), (
        f'{doc_slug} documents an unreachable 201 for PUT'
    )


def test_put_advertises_201_where_the_fallback_is_reachable():
    """LookupTableResource's obj_update raises tastypie's own NotFound
    for a missing table, so the create-on-PUT fallback is real."""
    entry = ApiEntry(
        fixtures_v0_1.LookupTableResource, 'v1', 'lookup-table-v1'
    )
    put = resource_paths(entry)[
        '/a/{domain}/api/lookup_table/v1/{pk}/'
    ]['put']
    assert '201' in put['responses']


def test_user_v1_documents_language_and_role_as_writable():
    """language and role are real fields CommcareUserUpdates.update()
    dispatches, but neither is a declared Tastypie field, so without a
    added_fields entry (like password's) neither would appear in
    the request body at all."""
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    paths = resource_paths(entry)
    for path, method in (
        ('/a/{domain}/api/user/v1/', 'post'),
        ('/a/{domain}/api/user/v1/{pk}/', 'put'),
    ):
        schema = paths[path][method]['requestBody']['content'][
            'application/json'
        ]['schema']
        for name in ('language', 'role'):
            assert name in schema['properties']
            assert schema['properties'][name]['writeOnly'] is True


def test_user_v1_description_documents_account_confirmation_constraints():
    """validate_new_user_input() enforces that password is omitted and
    email is provided when require_account_confirmation is set, and
    _update_phone_numbers() makes the first phone_numbers entry the
    default. These preconditions used to live on mobile-worker.rst,
    which this branch reduces to a stub; they must survive somewhere a
    reader of the generated spec will see them."""
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    operation = resource_paths(entry)['/a/{domain}/api/user/v1/']['post']
    description = operation['description']
    assert 'require_account_confirmation' in description
    assert 'password' in description
    assert 'email' in description
    assert 'default_phone_number' in description


def test_declared_list_example_is_attached():
    entry = ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1')
    operation = resource_paths(entry)['/a/{domain}/api/user/v1/']['get']
    content = operation['responses']['200']['content']['application/json']
    assert content['example']['objects'][0]['username']


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


@pytest.mark.parametrize(
    'entry', documented_entries(), ids=lambda entry: entry.doc_slug
)
def test_every_documented_resource_files_its_field_docs_correctly(entry):
    """``field_schemas`` overrides a field tastypie declares; ``added_fields``
    describes one it does not. Filing an entry under the wrong key is how a
    mistyped field name used to go unnoticed, so check every resource rather
    than waiting for a spec rebuild to surface it."""
    resource = entry.resource(api_name=entry.version)
    reject_misfiled_docs(entry.resource, collect_docs(entry.resource),
                         resource.build_schema())


def test_an_unauthenticated_resource_publishes_empty_security():
    """An empty list is OpenAPI's explicit "this operation needs no
    authentication"; omitting the key would inherit the document-wide
    requirement and advertise an API key that is never checked."""
    from corehq.apps.api.openapi.catalogue import ApiEntry
    from corehq.apps.api.resources.v0_4 import SingleSignOnResource

    entry = ApiEntry(SingleSignOnResource, 'v1', 'sso-v1')
    operation = resource_paths(entry)['/a/{domain}/api/sso/v1/']['post']
    assert operation['security'] == []


def test_an_authenticated_resource_inherits_document_security():
    from corehq.apps.api.openapi.catalogue import ApiEntry
    from corehq.apps.api.resources.v0_5 import CommCareUserResource

    entry = ApiEntry(CommCareUserResource, 'v1', 'user-v1')
    paths = resource_paths(entry)
    operation = paths['/a/{domain}/api/user/v1/']['get']
    assert 'security' not in operation


def test_a_declared_request_body_overrides_the_derived_one():
    """SingleSignOnResource reads request.POST, so its body is
    form-encoded rather than the JSON the generic path would publish."""
    from corehq.apps.api.openapi.catalogue import ApiEntry
    from corehq.apps.api.resources.v0_4 import SingleSignOnResource

    entry = ApiEntry(SingleSignOnResource, 'v1', 'sso-v1')
    operation = resource_paths(entry)['/a/{domain}/api/sso/v1/']['post']
    content = operation['requestBody']['content']
    assert list(content) == ['application/x-www-form-urlencoded']
    assert content['application/x-www-form-urlencoded']['schema'][
        'required'
    ] == ['username', 'password']
