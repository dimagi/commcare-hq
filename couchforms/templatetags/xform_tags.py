import types
from datetime import date, datetime
from django import template
from couchforms import util
from django.utils.html import escape
from couchforms.models import XFormInstance

register = template.Library()

@register.simple_tag
def value_for_display(value):
    return util.value_for_display(value)

@register.simple_tag
def render_form_data(form):

    def render_node(nodekey, nodevalue, show_hidden=True):

        def is_hidden_field(field_key):
            # hackity hack this static list of things we don't actually
            # want to display
            if show_hidden: return False
            SYSTEM_FIELD_NAMES = ("drugs_prescribed", "case", "meta", "clinic_ids", "drug_drill_down", "tmp", "info_hack_done")
            return field_key.startswith("#") or field_key.startswith("@") or field_key.startswith("_") \
                   or field_key.lower() in SYSTEM_FIELD_NAMES

        def format_name(value):
            if not isinstance(value, basestring):
                value = unicode(value)
            return value.replace("_", " ")

        def render_base_type(key, value):
            if not value: return ""
            return "<li><span class='prompt'>%s:</span> <span class='value'>%s</span></li>" % (format_name(key), format_name(value))


        def is_base_type(value):
            return isinstance(value, basestring) or \
                   isinstance(value, date) or \
                   isinstance(value, datetime)

        if not nodevalue or is_hidden_field(nodekey): return ""
        if is_base_type(nodevalue):
            return render_base_type(nodekey, nodevalue)
        else:
            header = '<li class="group">%s</li>' % format_name(nodekey)
            # process a dictionary
            if isinstance(nodevalue, types.DictionaryType):
                node_list = []
                for key, value in nodevalue.items() :
                    # recursive call
                    node = render_node(key, value)
                    if node: node_list.append(node)

                if node_list:
                    return '%(header)s<ul>%(body)s</ul>' % \
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

    return "<ul id='formdata'>%s</ul>" % "".join(render_node(key, val) for key, val in form.top_level_tags().items())

@register.simple_tag
def render_form_xml(form):
    return '<pre id="formxml">%s</pre>' % escape(form.get_xml())

@register.simple_tag
def form_inline_display(form_id):
    if form_id:
        form = XFormInstance.get(form_id)
        if form:
            return "%s: %s" % (form.received_on.date(), form.xmlns)
        return "missing form: %s" % form_id
    return "empty form id found"
