from __future__ import absolute_import

import doctest
from unittest import skipUnless

import six
from django.test import SimpleTestCase

from corehq.motech.value_source import ValueSource
from dimagi.ext.couchdbkit import (
    DocumentSchema,
    SchemaDictProperty,
    SchemaProperty,
)


class Foo(DocumentSchema):
    """
    Demonstrates the difference between DocumentSchema, SchemaProperty
    and SchemaDictProperty:

    >>> foo = dict(Foo.wrap({}))
    >>> sorted(list(foo.keys()))
    ['doc_type', 'valuesource_dict_prop', 'valuesource_prop']

    Note 'valuesource' is not in dict(foo)

    >>> foo['valuesource_prop']
    ValueSource(doc_type=u'ValueSource')
    >>> foo['valuesource_dict_prop']
    {}

    """
    valuesource = ValueSource(required=False)
    valuesource_prop = SchemaProperty(ValueSource, required=False)
    valuesource_dict_prop = SchemaDictProperty(ValueSource, required=False)


@skipUnless(six.PY2, 'Doctest includes Py2 string representation')
class DocTests(SimpleTestCase):

    def test_doctests(self):
        from corehq.motech.tests import test_schema

        results = doctest.testmod(test_schema)
        self.assertEqual(results.attempted, 4)
        self.assertEqual(results.failed, 0)
