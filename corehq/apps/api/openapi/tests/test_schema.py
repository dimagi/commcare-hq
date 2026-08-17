import pytest
from tastypie.fields import NOT_PROVIDED

from corehq.apps.api.openapi.schema import TYPE_MAP, field_to_schema


def field_info(**overrides):
    info = {
        'type': 'string',
        'nullable': False,
        'blank': False,
        'readonly': False,
        'unique': False,
        'primary_key': False,
        'default': NOT_PROVIDED,
        'help_text': 'Unicode string data. Ex: "Hello World"',
        'verbose_name': 'thing',
    }
    info.update(overrides)
    return info


@pytest.mark.parametrize(
    'dehydrated_type, expected',
    [
        ('string', {'type': 'string'}),
        ('integer', {'type': 'integer'}),
        ('float', {'type': 'number'}),
        ('decimal', {'type': 'string', 'format': 'decimal'}),
        ('boolean', {'type': 'boolean'}),
        ('list', {'type': 'array', 'items': {}}),
        ('dict', {'type': 'object', 'additionalProperties': True}),
        ('date', {'type': 'string', 'format': 'date'}),
        ('datetime', {'type': 'string', 'format': 'date-time'}),
        ('time', {'type': 'string', 'format': 'time'}),
        ('related', {'type': 'string', 'format': 'uri'}),
    ],
)
def test_every_dehydrated_type_maps(dehydrated_type, expected):
    assert field_to_schema(field_info(type=dehydrated_type)) == expected


def test_unknown_type_falls_back_to_permissive_schema():
    assert field_to_schema(field_info(type='mystery')) == {}


def test_nullable_uses_openapi_30_spelling():
    schema = field_to_schema(field_info(nullable=True))
    assert schema == {'type': 'string', 'nullable': True}


def test_readonly_field():
    schema = field_to_schema(field_info(readonly=True))
    assert schema == {'type': 'string', 'readOnly': True}


def test_documented_help_text_becomes_the_description():
    schema = field_to_schema(field_info(help_text='The primary phone number.'))
    assert schema['description'] == 'The primary phone number.'


def test_generic_help_text_produces_no_description():
    assert 'description' not in field_to_schema(field_info())


def test_not_provided_default_is_omitted():
    assert 'default' not in field_to_schema(field_info())


def test_concrete_default_is_included():
    schema = field_to_schema(field_info(type='boolean', default=False))
    assert schema['default'] is False


def test_callable_default_is_omitted():
    schema = field_to_schema(field_info(default=lambda: 'x'))
    assert 'default' not in schema


def test_override_replaces_generated_keys():
    schema = field_to_schema(
        field_info(type='list'),
        override={'items': {'type': 'string'}},
    )
    assert schema == {'type': 'array', 'items': {'type': 'string'}}


def test_type_map_covers_all_tastypie_types():
    from tastypie import fields as tastypie_fields

    declared = {
        value.dehydrated_type
        for value in vars(tastypie_fields).values()
        if isinstance(value, type)
        and issubclass(value, tastypie_fields.ApiField)
    }
    assert declared <= set(TYPE_MAP)
