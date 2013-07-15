from couchdbkit import StringProperty, BooleanProperty, IntegerProperty, FloatProperty, DecimalProperty, DictProperty, StringListProperty, SchemaListProperty, SchemaDictProperty, DateProperty, DateTimeProperty, SchemaProperty
from casexml.apps.case.models import CommCareCase
from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING

def type_full_date(formats=DATE_FORMATS_STRING):
    return dict(type="date", format=formats)


def prop_subtype(prop_type, nested=False, dynamic=False, sub_types=None):
    #schemalist, schemadict
    sub_types = sub_types or default_special_types
    return {
        'type': 'nested' if nested else 'object',
        'dynamic': dynamic,
        'properties': set_properties(prop_type, custom_types=sub_types)
    }


simple_type_mapper = {
    StringProperty: dict(type="string"),
    BooleanProperty: dict(type="boolean"),
    IntegerProperty: dict(type="long"),
    FloatProperty: dict(type="float"),
    DecimalProperty: dict(type="double"),
    StringListProperty: dict(type="string"),
    DateTimeProperty: type_full_date(),
    DateProperty: type_full_date(),
    #TimeProperty: type_full_date,
}

complex_type_mapper = {
    SchemaListProperty: prop_subtype,
    SchemaDictProperty: prop_subtype,
    SchemaProperty: prop_subtype,
}

conservative_types = {
    DictProperty: {"type": "object", "dynamic": False}
}




def type_exact_match_string(prop_name, dual=True):
    """
    Mapping for fields that may want prefixes (based upon the default tokenizer which splits by -'s)
    Or the full exact string (like domains)
    """
    if dual:
        return {
            "type": "multi_field",
            "fields": {
                prop_name: {"type": "string", "index": "analyzed"},
                "exact": {"type": "string", "index": "not_analyzed"}
            }
        }
    else:
        return dict(type="string")


default_special_types = {
    "domain":type_exact_match_string("domain", dual=True),
    #to extend, use this and add special formats here...
}

default_nested_types = []

case_special_types = {
    "domain": type_exact_match_string("domain", dual=True),
    "name": type_exact_match_string("name", dual=True),
    "external_id": type_exact_match_string("external_id", dual=True),
    "xform_ids": {"type": "string", "index": "not_analyzed"},
    "xform_id": {"type": "string", "index": "not_analyzed"},
    "referrals": {"enabled": False, "type": "object"},
    "computed_": {"enabled": False, "type": "object"},
    "type":type_exact_match_string("type", dual=True),
    #to extend, use this and add special date formats here...
}

case_nested_types = ['actions']

domain_special_types = {
    "name": type_exact_match_string("name", dual=True),
    "author": type_exact_match_string("author", dual=True),
    "title": type_exact_match_string("title", dual=True),
    "short_description": type_exact_match_string("short_description", dual=True),
    "project_type": {"type": "string", "analyzer": "comma"},
    "__sub_types": {
        "deployment": {
            "country": type_exact_match_string("country", dual=True),
            "region": type_exact_match_string("region", dual=True),
            "city": type_exact_match_string("city", dual=True),
            "description": type_exact_match_string("description", dual=True),
        },
        "internal": {
            "area": type_exact_match_string("area", dual=True),
            "sub_area": type_exact_match_string("sub_area", dual=True),
            "initiative": type_exact_match_string("initiative", dual=True),
        },
        "cda": {
            "type": {"type": "string", "index": "not_analyzed"},
        }
    }
}

def set_properties(schema_class, custom_types=default_special_types, nested_types=default_nested_types, init_dict=None):
    """
    Helper function to walk a schema_class's properties recursively and create a typed out mapping
    that can index well (specifically dict types and date time properties)
    """
    props_dict = init_dict or {}
    for prop_name, prop_type in schema_class.properties().items():
        if custom_types.has_key(prop_name):
            props_dict[prop_name] = custom_types[prop_name]
        elif simple_type_mapper.has_key(prop_type.__class__):
            props_dict[prop_name] = simple_type_mapper[prop_type.__class__]
        elif complex_type_mapper.has_key(prop_type.__class__):
            func = complex_type_mapper[prop_type.__class__]
            sub_types = custom_types.get("__sub_types", {}).get(prop_name)
            props_dict[prop_name] = func(prop_type._schema, nested=prop_name in nested_types, dynamic=False, sub_types=sub_types)

    if not props_dict.get('doc_type'):
        props_dict["doc_type"] = {"type": "string", "index": "not_analyzed"}
    return props_dict



#A conservative mapping - don't detect datestring we don't know about
#but try to always add to mapping additional properties of dicts we didn't expect (from DictProperties)
DEFAULT_MAPPING_WRAPPER = {
        "date_detection": False,
        'dynamic': False,
        "date_formats": DATE_FORMATS_ARR, #for parsing the explicitly defined dates
        "_meta": {"created": None},
        "properties": {}
    }

def case_mapping_generator():
    #todo: need to ensure that domain is always mapped
    m = DEFAULT_MAPPING_WRAPPER
    doc_class=CommCareCase
    m['properties'] = set_properties(doc_class, custom_types=case_special_types)
    return m