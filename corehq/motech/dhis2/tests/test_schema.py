import doctest
import json

from schema import Schema

from django.conf import settings

from corehq.motech.dhis2.schema import get_tracked_entity_schema

DATA_DIR = settings.BASE_DIR + '/corehq/motech/dhis2/tests/data/'


def test_tracked_entity_instance_1():
    filename = DATA_DIR + 'tracked_entity_instance_1.json'
    with open(filename) as fp:
        doc = json.load(fp)
    schema = get_tracked_entity_schema()
    Schema(schema).validate(doc)


def test_doctests():
    from corehq.motech.dhis2 import schema

    results = doctest.testmod(schema)
    assert results.failed == 0
