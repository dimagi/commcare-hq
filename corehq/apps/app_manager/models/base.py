import random
import types

from dimagi.ext.couchdbkit import (
    DictProperty,
    DocumentSchema,
    StringProperty,
)
from jsonpath_ng import jsonpath, parse


class LabelProperty(DictProperty):
    """Stores a {lang_code: translated_string} dict"""


# store a list of references to form ID's so that
# when an app is copied we can update the references
# with the new values
form_id_references = []


def FormIdProperty(*expressions, **kwargs):
    """
    Create a StringProperty that references a form ID. This is necessary because
    form IDs change when apps are copied so we need to make sure we update
    any references to the them.
    :param expression:  jsonpath expression that can be used to find the field
    :param kwargs:      arguments to be passed to the underlying StringProperty
    """
    for expression in expressions:
        path_expression = parse(expression)
        assert isinstance(path_expression, jsonpath.Child), "only child path expressions are supported"
        field = path_expression.right
        assert len(field.fields) == 1, 'path expression can only reference a single field'
        form_id_references.append(path_expression)
    return StringProperty(**kwargs)


def rename_key(dct, old, new):
    if old in dct:
        if new in dct and dct[new]:
            dct["%s_backup_%s" % (new, hex(random.getrandbits(32))[2:-1])] = dct[new]
        dct[new] = dct[old]
        del dct[old]


class IndexedSchema(DocumentSchema):
    """
    Abstract class.
    Meant for documents that appear in a list within another document
    and need to know their own position within that list.

    """

    def with_id(self, i, parent):
        self._i = i
        self._parent = parent
        return self

    @property
    def id(self):
        return self._i

    def __eq__(self, other):
        return (
            other and isinstance(other, IndexedSchema)
            and (self.id == other.id)
            and (self._parent == other._parent)
        )

    class Getter(object):

        def __init__(self, attr):
            self.attr = attr

        def __call__(self, instance):
            items = getattr(instance, self.attr)
            length = len(items)
            for i, item in enumerate(items):
                yield item.with_id(i % length, instance)

        def __get__(self, instance, owner):
            # thanks, http://metapython.blogspot.com/2010/11/python-instance-methods-how-are-they.html
            # this makes Getter('foo') act like a bound method
            return types.MethodType(self, instance)


# It's a shame to have both Assertion and CustomAssertion, as they're
# essentially the same, but some usages of Assertion are optional
# SchemaPropertys, and marking `test` as required precludes that. Setting the
# SchemaProperty itself as optional doesn't work
# https://github.com/dimagi/commcare-hq/pull/31885#discussion_r918391347
class Assertion(DocumentSchema):
    """Parallel of the Assertion xml entity in the suite file"""
    test = StringProperty()
    text = DictProperty(StringProperty)

    @property
    def has_text(self):
        return any(self.text.values())


class CustomAssertion(Assertion):
    """Custom assertions to add to the assertions block
    test: The actual assertion to run
    locale_id: The id of the localizable string
    """
    test = StringProperty(required=True)
