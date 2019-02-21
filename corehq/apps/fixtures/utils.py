from __future__ import absolute_import
from __future__ import unicode_literals
import re
from xml.etree import cElementTree as ElementTree

from celery.task import task
from dimagi.utils.chunked import chunked
from corehq.blobs import get_blob_db

BAD_SLUG_PATTERN = r"([/\\<>\s])"


def clean_fixture_field_name(field_name):
    """Effectively slugifies a fixture's field name so that we don't send
    bad XML back from the phone. Ideally, the fixture name should be
    verified as a good slug before using it.
    """
    subbed_string = re.sub(BAD_SLUG_PATTERN, '_', field_name)
    if subbed_string.startswith('xml'):
        subbed_string = subbed_string.replace('xml', '_', 1)
    return subbed_string


def is_identifier_invalid(name):
    """
    Determine if given name is an invalid XML identifier:
    - Blank
    - Contains special characters
    - Start with "xml"
    - Start with a number
    """
    if (not bool(name) or name.startswith('xml')):
        return True

    try:
        ElementTree.fromstring('<{} />'.format(name).encode('utf-8'))
    except ElementTree.ParseError:
        return True

    return False


def get_fields_without_attributes(fields):
    fields_without_attributes = []
    for fixture_field in fields:
        fields_without_attributes.append(fixture_field.field_name)
    return fields_without_attributes


def get_index_schema_node(fixture_id, attrs_to_index):
    """
    Assemble a schema node to tell mobile how to index a fixture.
    """
    indices_node = ElementTree.Element('indices')
    for index_attr in sorted(attrs_to_index):  # sorted only for tests
        element = ElementTree.Element('index')
        element.text = index_attr
        indices_node.append(element)
    node = ElementTree.Element('schema', {'id': fixture_id})
    node.append(indices_node)
    return node


def clear_fixture_cache(domain):
    from corehq.apps.fixtures.models import FIXTURE_BUCKET
    get_blob_db().delete(key=FIXTURE_BUCKET + '/' + domain)


@task(queue='background_queue')
def remove_deleted_ownerships(deleted_fixture_ids, domain):
    from corehq.apps.fixtures.models import FixtureOwnership
    for fixture_ids in chunked(deleted_fixture_ids, 100):
        bad_ownerships = FixtureOwnership.for_all_item_ids(fixture_ids, domain)
        FixtureOwnership.get_db().bulk_delete(bad_ownerships)
