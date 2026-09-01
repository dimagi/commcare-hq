from corehq.apps.api.openapi.emit import (
    is_detail_path,
    operation,
    path_parameters,
    request_body,
)


def test_a_path_ending_in_a_parameter_is_a_detail_path():
    assert is_detail_path('/a/{domain}/api/case/v2/{case_id}/')
    assert is_detail_path('/a/{domain}/api/case/v2/ext/{external_id}/')


def test_a_collection_path_is_not_a_detail_path():
    assert not is_detail_path('/a/{domain}/api/case/v2/')
    assert not is_detail_path('/a/{domain}/api/case/v2/bulk-fetch/')


def test_path_parameters_are_derived_from_the_path():
    assert path_parameters('/a/{domain}/api/case/v2/{case_id}/') == [
        {
            'name': 'case_id',
            'in': 'path',
            'required': True,
            'schema': {'type': 'string'},
        }
    ]


def test_domain_is_excluded_because_every_path_item_already_carries_it():
    assert path_parameters('/a/{domain}/api/case/v2/') == []


def test_domain_is_excluded_even_when_mixed_with_other_parameters():
    # Pins that {domain} is dropped wherever it appears in the path,
    # while the other parameter(s) are kept, in path order.
    assert path_parameters(
        '/a/{domain}/api/case/v2/{case_id}/ext/{external_id}/'
    ) == [
        {
            'name': 'case_id',
            'in': 'path',
            'required': True,
            'schema': {'type': 'string'},
        },
        {
            'name': 'external_id',
            'in': 'path',
            'required': True,
            'schema': {'type': 'string'},
        },
    ]


def test_multiple_parameters_are_returned_in_path_order():
    assert path_parameters('/x/{first}/y/{second}/') == [
        {
            'name': 'first',
            'in': 'path',
            'required': True,
            'schema': {'type': 'string'},
        },
        {
            'name': 'second',
            'in': 'path',
            'required': True,
            'schema': {'type': 'string'},
        },
    ]


def test_a_description_is_attached_when_one_is_supplied():
    [param] = path_parameters(
        '/a/{domain}/api/case/v2/{case_id}/',
        {'case_id': 'Unique identifier of the record.'},
    )
    assert param['description'] == 'Unique identifier of the record.'


def test_an_empty_description_is_omitted_not_emitted():
    # An empty description renders as one in the reference pages.
    [param] = path_parameters('/x/{pk}/', {'pk': ''})
    assert 'description' not in param


def test_operation_omits_an_empty_description():
    op = operation('Cases', 'case_v1_list_get', 'case', {'200': {}}, '')
    assert 'description' not in op
    assert op == {
        'summary': 'Cases',
        'operationId': 'case_v1_list_get',
        'tags': ['case'],
        'responses': {'200': {}},
    }


def test_operation_emits_explicit_empty_security_but_omits_none():
    assert 'security' not in operation('S', 'i', 't', {}, '', security=None)
    assert operation('S', 'i', 't', {}, '', security=[])['security'] == []


def test_request_body_is_required_json():
    assert request_body({'type': 'object'}) == {
        'required': True,
        'content': {'application/json': {'schema': {'type': 'object'}}},
    }


def test_request_body_carries_an_example_when_one_is_given():
    body = request_body({'type': 'object'}, {'case_name': 'Harmon'})
    assert body['content']['application/json'] == {
        'schema': {'type': 'object'},
        'example': {'case_name': 'Harmon'},
    }


def test_a_falsy_example_is_still_published():
    # An empty list is a meaningful example for a bulk endpoint: it says the
    # request body may be empty. `if example is not None` keeps it.
    body = request_body({'type': 'array'}, [])
    assert body['content']['application/json']['example'] == []
