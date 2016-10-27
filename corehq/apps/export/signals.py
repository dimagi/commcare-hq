from django import dispatch

from .dbaccessors import get_inferred_schema
from .models import MAIN_TABLE, PathNode


def add_inferred_export_properties(sender, domain, case_type, properties, **kwargs):
    """
    Adds inferred properties to the inferred schema for a case type.

    :param: sender - The signal sender
    :param: domain
    :param: case_type
    :param: properties - An iterable of case properties to add to the inferred schema
    """
    inferred_schema = get_inferred_schema(domain, case_type)
    group_schema = inferred_schema.put_group_schema(MAIN_TABLE)

    for case_property in properties:
        group_schema.put_item([PathNode(name=case_property)])
    inferred_schema.save()

added_inferred_export_properties = dispatch.Signal(providing_args=['properties'])
added_inferred_export_properties.connect(add_inferred_export_properties)
