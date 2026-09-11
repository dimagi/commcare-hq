import pytest

from corehq.apps.api.openapi.docs import (
    GENERIC_HELP_TEXTS,
    collect_docs,
    field_description,
    reject_misfiled_docs,
)


class Base:
    class Docs:
        summary = 'Base summary'
        description = 'Base description'
        examples = {'list': 'base/list.json'}
        field_schemas = {'a': {'type': 'string'}}


class Child(Base):
    class Docs:
        summary = 'Child summary'
        examples = {'detail': 'child/detail.json'}
        field_schemas = {'b': {'type': 'integer'}}


class Grandchild(Child):
    pass


def test_subclass_overrides_scalar_and_merges_dicts():
    docs = collect_docs(Child)
    assert docs['summary'] == 'Child summary'
    assert docs['description'] == 'Base description'
    assert docs['examples'] == {
        'list': 'base/list.json',
        'detail': 'child/detail.json',
    }
    assert docs['field_schemas'] == {
        'a': {'type': 'string'},
        'b': {'type': 'integer'},
    }


def test_class_without_its_own_docs_inherits_the_merge():
    assert collect_docs(Grandchild) == collect_docs(Child)


def test_class_with_no_docs_anywhere():
    class Bare:
        pass

    assert collect_docs(Bare) == {}


def test_tastypie_and_hq_class_defaults_are_generic():
    assert 'Unicode string data. Ex: "Hello World"' in GENERIC_HELP_TEXTS
    assert 'A UUID object' in GENERIC_HELP_TEXTS


def test_field_description_rejects_generic_and_empty_text():
    assert field_description(None) is None
    assert field_description('') is None
    assert field_description('Integer data. Ex: 2673') is None
    assert field_description('A UUID object') is None
    assert field_description("The user's login name.") == (
        "The user's login name."
    )


def test_a_misspelled_docs_key_is_an_error_not_a_silent_omission():
    """The failure this prevents is invisible in the generated spec: a
    resource whose ``field_schema`` (singular) was ignored looks exactly
    like one that declared nothing."""
    class Resource:
        class Docs:
            summary = 'Fine.'
            field_schema = {'name': {'type': 'string'}}

    with pytest.raises(ValueError, match='field_schema'):
        collect_docs(Resource)


def test_known_keys_and_dunders_are_accepted():
    class Resource:
        class Docs:
            summary = 'Fine.'
            field_schemas = {'name': {'type': 'string'}}

    assert collect_docs(Resource) == {
        'summary': 'Fine.',
        'field_schemas': {'name': {'type': 'string'}},
    }


class Resource:
    """Stands in for a tastypie resource in the misfiling tests."""


SCHEMA = {'fields': {'name': {'type': 'string'}}}


def test_a_field_schemas_key_naming_no_declared_field_is_an_error():
    """A typo here used to be published as a phantom property (if it
    carried a ``type``) or dropped without a word (if it did not)."""
    docs = {'field_schemas': {'nmae': {'type': 'string'}}}
    with pytest.raises(ValueError, match='nmae.*belongs in added_fields'):
        reject_misfiled_docs(Resource, docs, SCHEMA)


def test_an_added_fields_key_naming_a_declared_field_is_an_error():
    docs = {'added_fields': {'name': {'type': 'string'}}}
    with pytest.raises(ValueError, match='name.*through field_schemas'):
        reject_misfiled_docs(Resource, docs, SCHEMA)


def test_both_kinds_of_misfiling_are_reported_together():
    docs = {
        'field_schemas': {'nmae': {'type': 'string'}},
        'added_fields': {'name': {'type': 'string'}},
    }
    with pytest.raises(ValueError) as excinfo:
        reject_misfiled_docs(Resource, docs, SCHEMA)
    assert 'nmae' in str(excinfo.value)
    assert 'added_fields names field(s)' in str(excinfo.value)


@pytest.mark.parametrize('docs', [
    {},
    {'field_schemas': {'name': {'description': 'The name.'}}},
    {'added_fields': {'derived': {'type': 'string'}}},
    {
        'field_schemas': {'name': {'description': 'The name.'}},
        'added_fields': {'derived': {'type': 'string'}},
    },
])
def test_correctly_filed_declarations_are_accepted(docs):
    reject_misfiled_docs(Resource, docs, SCHEMA)
