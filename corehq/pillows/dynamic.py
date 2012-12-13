from couchdbkit import StringProperty, BooleanProperty, IntegerProperty, FloatProperty, DecimalProperty, ListProperty, DictProperty, StringListProperty, SchemaListProperty, SchemaDictProperty, DateProperty, DateTimeProperty
import simplejson
from casexml.apps.case.models import CommCareCase
from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING

def type_full_date(formats=DATE_FORMATS_STRING):
    return dict(type="date", format=formats)


def prop_subtype(prop_type, nested=False, dynamic=False):
    #schemalist, schemadict
    ret = dict()
    if nested:
        ret['type'] = "nested"
    else:
        ret['type'] = "object"
    ret['dynamic'] = dynamic
    ret['properties'] = set_properties(prop_type)
    return ret


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
    }

conservative_types = {
    DictProperty: {"type": "object", "dynamic": False}
}




def type_exact_match_string(prop_name, dual=True):
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
    #special date formats here...
}

case_special_types = {
    "domain":type_exact_match_string("domain", dual=True),
    "xform_ids": {"type": "string", "index": "not_analyzed"},
    "xform_id": {"type": "string", "index": "not_analyzed"},
    #special date formats here...
}

def set_properties(schema_class, custom_types=default_special_types):
    props_dict = {}
    for prop_name, prop_type in schema_class.properties().items():
        if custom_types.has_key(prop_name):
            props_dict[prop_name] = custom_types[prop_name]
            continue

        if simple_type_mapper.has_key(prop_type.__class__):
            props_dict[prop_name] = simple_type_mapper[prop_type.__class__]
            continue

        if complex_type_mapper.has_key(prop_type.__class__):
            func = complex_type_mapper[prop_type.__class__]
            props_dict[prop_name] = func(prop_type._schema, nested=False, dynamic=False)
            continue
#        print prop_name
    return props_dict
#    print simplejson.dumps(m, indent=4)

DEFAULT_MAPPING_WRAPPER = {
        "date_detection": False,
        'dynamic': True,
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