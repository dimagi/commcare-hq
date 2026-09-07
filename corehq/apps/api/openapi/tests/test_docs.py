from corehq.apps.api.openapi.docs import (
    collect_docs,
    field_description,
    GENERIC_HELP_TEXTS,
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
