from django import dispatch

from .dbaccessors import get_inferred_schema
from .system_properties import (
    MAIN_CASE_TABLE_PROPERTIES
)
from .models import MAIN_TABLE, PathNode, InferredSchema, ScalarItem


def add_inferred_export_properties(sender, domain=None, case_type=None, properties=None, **kwargs):
    """
    Adds inferred properties to the inferred schema for a case type.

    :param: sender - The signal sender
    :param: domain
    :param: case_type
    :param: properties - An iterable of case properties to add to the inferred schema
    """

    assert domain, 'Must have domain'
    assert case_type, 'Must have case type'
    assert all(map(lambda prop: '.' not in prop, properties)), 'Properties should not have periods'
    inferred_schema = get_inferred_schema(domain, case_type)
    if not inferred_schema:
        inferred_schema = InferredSchema(
            domain=domain,
            case_type=case_type,
        )
    group_schema = inferred_schema.put_group_schema(MAIN_TABLE)

    for case_property in properties:
        path = [PathNode(name=case_property)]
        system_property_column = filter(
            lambda column: column.item.path == path,
            MAIN_CASE_TABLE_PROPERTIES,
        )

        if system_property_column:
            assert len(system_property_column) == 1
            column = system_property_column[0]
            group_schema.put_item(path, inferred_from=sender, item_cls=column.item.__class__)
        else:
            group_schema.put_item(path, inferred_from=sender, item_cls=ScalarItem)

    inferred_schema.save()

added_inferred_export_properties = dispatch.Signal(providing_args=['domain', 'case_type', 'properties'])
added_inferred_export_properties.connect(add_inferred_export_properties)
