import re
from datetime import datetime
from lxml.etree import Element
from xml.etree import cElementTree as ElementTree
from uuid import UUID

from corehq.blobs import get_blob_db
from corehq.apps.fixtures.models import LookupTable

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
    if (not name or str(name).startswith('xml')):
        return True

    try:
        Element(name)
    except (ValueError, TypeError):
        return True

    return False


def get_fields_without_attributes(fields):
    return [f.field_name for f in fields]


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


def clear_fixture_cache(domain, data_type_ids):
    assert not isinstance(data_type_ids, (str, UUID)), f'expected list or set, got {type(data_type_ids).__name__}'
    LookupTable.objects.filter(id__in=data_type_ids).update(last_modified=datetime.utcnow())
    from corehq.apps.fixtures.models import fixture_bucket
    for data_type_id in data_type_ids:
        get_blob_db().delete(key=fixture_bucket(data_type_id, domain))
