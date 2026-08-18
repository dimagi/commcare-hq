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
    'parameters',
    'extra_operations',
    'list_write_responses',
    'detail_write_responses',
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
        for key in DOCS_KEYS:
            value = docs.__dict__.get(key)
            if value is None:
                continue
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
    return merged


def field_description(help_text):
    """The field's description, or ``None`` if it is undocumented."""
    if not help_text or help_text in GENERIC_HELP_TEXTS:
        return None
    return help_text
