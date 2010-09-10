import types
from datetime import date, datetime
from django import template
from couchforms import util 

register = template.Library()

@register.simple_tag
def value_for_display(value):
    return util.value_for_display(value)

@register.simple_tag
def render_form_data(form):
    
    def render_node(nodekey, nodevalue):
        
        def is_hidden_field(field_key):
            SYSTEM_FIELD_NAMES = ("drugs_prescribed", "case", "meta", "clinic_ids", "drug_drill_down", "tmp") 
            return field_key.startswith("#") or field_key.startswith("@") or field_key.startswith("_") \
                   or field_key.lower() in SYSTEM_FIELD_NAMES
                    
        def format_name(value):
            return str(value).replace("_", " ")
        
        def render_base_type(key, value):
            if not value: return ""
            return "<li>%s: <b>%s</b></li>" % (format_name(key), format_name(value))
            
        
        def is_base_type(value):
            return isinstance(value, basestring) or \
                   isinstance(value, date) or \
                   isinstance(value, datetime)
        
        if not nodevalue or is_hidden_field(nodekey): return ""
        if is_base_type(nodevalue):
            return render_base_type(nodekey, nodevalue)
        else:
            header = "<li>%s</li>" % format_name(nodekey)
            # process a dictionary
            if isinstance(nodevalue, types.DictionaryType):
                node_list = []
                for key, value in nodevalue.items() :
                    # recursive call
                    node = render_node(key, value)
                    if node: node_list.append(node)
                        
                if node_list:
                    return "%(header)s<ul>%(body)s</ul>" % \
                            {"header": header,
                             "body": "".join(node_list)}
                else:
                    return ""
            elif isinstance(nodevalue, types.ListType) or \
                 isinstance(nodevalue, types.TupleType):
                # the only thing we are allowed to have lists of
                # is dictionaries
                full_list = []
                for item in nodevalue:
                    node_list = []
                    if is_base_type(item):
                        node_list.append("<li>%s</li>" % format_name(item))
                    elif isinstance(item, types.DictionaryType):
                        for key, value in item.items():
                            node = render_node(key, value)
                            if node:
                                node_list.append(node)
                    else:
                        node_list.append("<li>%s</li>" % format_name(str(item)))
                    full_list.append("%(header)s<ul>%(body)s</ul>" % \
                                     {"header": header,
                                      "body": "".join(node_list)})
                return "".join(full_list)
            else:
                return render_base_type(nodekey, nodevalue)
    
    return "<ul>%s</ul>" % "".join(render_node(key, val) for key, val in form.top_level_tags().items())
