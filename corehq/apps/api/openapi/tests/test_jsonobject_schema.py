import jsonobject

from corehq.apps.api.openapi.jsonobject_schema import jsonobject_to_schema
from corehq.apps.hqcase.api.updates import JsonCaseCreation, JsonIndex


def test_string_properties_and_choices():
    schema = jsonobject_to_schema(JsonIndex)
    assert schema['type'] == 'object'
    assert schema['properties']['case_id'] == {'type': 'string'}
    assert schema['properties']['relationship'] == {
        'type': 'string',
        'enum': ['child', 'extension'],
    }


def test_required_properties_are_listed():
    schema = jsonobject_to_schema(JsonCaseCreation)
    assert set(schema['required']) >= {
        'case_name',
        'case_type',
        'owner_id',
        'user_id',
    }


def test_boolean_and_dict_properties():
    schema = jsonobject_to_schema(JsonCaseCreation)
    assert schema['properties']['close'] == {
        'type': 'boolean',
        'default': False,
    }
    assert schema['properties']['properties']['type'] == 'object'


def test_nested_object_properties_recurse():
    schema = jsonobject_to_schema(JsonCaseCreation)
    indices = schema['properties']['indices']
    assert indices['type'] == 'object'
    assert indices['additionalProperties']['properties']['relationship'] == {
        'type': 'string',
        'enum': ['child', 'extension'],
    }


def test_a_computable_default_is_published():
    class WithDefault(jsonobject.JsonObject):
        greeting = jsonobject.StringProperty(default='hello')

    schema = jsonobject_to_schema(WithDefault)
    assert schema['properties']['greeting']['default'] == 'hello'


def test_an_uncomputable_default_is_omitted_not_guessed():
    """A default whose callable raises leaves the property with no
    ``default`` key, rather than failing the build or inventing a value.

    Nothing documented today has such a default -- see
    ``_default_value()`` -- so this pins the intended behaviour of a
    branch the real models never take.
    """
    def explode():
        raise RuntimeError('needs request context')

    class WithBadDefault(jsonobject.JsonObject):
        tricky = jsonobject.StringProperty(default=explode)

    schema = jsonobject_to_schema(WithBadDefault)
    assert schema['properties']['tricky'] == {'type': 'string'}
