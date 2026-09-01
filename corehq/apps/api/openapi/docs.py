"""Collection of hand-written API documentation held in the code.

Field descriptions use Tastypie's ``help_text``. Endpoint-level narrative
lives in a ``Docs`` inner class on the resource, which is merged across the
class hierarchy so that a subclass inherits its parent's documentation and
overrides only what it changes.
"""

from tastypie.fields import ApiField

DOCS_KEYS = (
    'summary',
    'description',
    'permissions',
    'examples',
    'field_schemas',
    'added_fields',
    'parameters',
    'extra_operations',
    'list_request_body',
    'list_write_responses',
    'detail_write_responses',
    'writable_fields',
    'put_creates_on_missing',
)


def _generic_help_texts():
    """Every ``help_text`` that is a field class default, not a description."""
    from corehq.apps.api import fields as hq_fields
    from tastypie import fields as tastypie_fields

    texts = set()
    for module in (tastypie_fields, hq_fields):
        for value in vars(module).values():
            if isinstance(value, type) and issubclass(value, ApiField):
                texts.add(value.help_text)
    return frozenset(texts)


GENERIC_HELP_TEXTS = _generic_help_texts()



def _reject_unknown_keys(resource_cls, docs):
    """Fail loudly on a declaration key this module does not read.

    ``collect_docs`` picks the keys it knows out of a ``Docs`` class, so
    anything else -- ``field_schema`` for ``field_schemas``, a key from a
    half-remembered convention -- is silently ignored, and the resource
    ships with documentation the author believes they wrote. There is no
    way to notice from the generated spec, because the missing content
    looks exactly like content that was never declared.
    """
    declared = {
        key
        for key in vars(docs)
        if not key.startswith('__') and not callable(vars(docs)[key])
    }
    unknown = sorted(declared - set(DOCS_KEYS))
    if unknown:
        raise ValueError(
            f'{resource_cls.__name__}.Docs declares unknown key(s) '
            f'{", ".join(unknown)}. Known keys: {", ".join(DOCS_KEYS)}.'
        )


def collect_docs(resource_cls):
    """Merge ``Docs`` inner classes across ``resource_cls``'s MRO.

    Subclasses win over base classes. Dict values are shallow-merged so that,
    for example, a subclass can add one example without restating the others.
    """
    merged = {}
    for klass in reversed(resource_cls.__mro__):
        docs = klass.__dict__.get('Docs')
        if docs is None:
            continue
        _reject_unknown_keys(klass, docs)
        for key in DOCS_KEYS:
            value = docs.__dict__.get(key)
            if value is None:
                continue
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
    return merged


def reject_misfiled_docs(resource_cls, docs, resource_schema):
    """Fail loudly on a field declaration filed under the wrong key.

    ``field_schemas`` overrides a field tastypie declares; ``added_fields``
    describes one it does not. Which one an entry belonged in used to be
    inferred from whether it carried a ``type``, so a mistyped field name
    was either published as a phantom property or dropped without a word --
    the same class of silent miss ``_reject_unknown_keys`` guards against
    one level up, and just as invisible from the generated spec.

    This is checked here rather than in ``collect_docs`` because it needs
    tastypie's ``build_schema()`` output, which only the caller has.
    """
    declared = set(resource_schema['fields'])
    errors = []
    unmatched = sorted(set(docs.get('field_schemas', {})) - declared)
    if unmatched:
        errors.append(
            f'field_schemas names field(s) the resource does not declare: '
            f'{", ".join(unmatched)}. A field tastypie does not declare '
            f'belongs in added_fields.'
        )
    matched = sorted(set(docs.get('added_fields', {})) & declared)
    if matched:
        errors.append(
            f'added_fields names field(s) the resource declares: '
            f'{", ".join(matched)}. A declared field is overridden through '
            f'field_schemas.'
        )
    if errors:
        raise ValueError(f'{resource_cls.__name__}.Docs: ' + ' '.join(errors))


def field_description(help_text):
    """The field's description, or ``None`` if it is undocumented."""
    if not help_text or help_text in GENERIC_HELP_TEXTS:
        return None
    return help_text
