import types
from datetime import date, datetime
from django import template
import pytz
from couchforms import util
from django.utils.html import escape
from couchforms.models import XFormInstance
from dimagi.utils.timezones import utils as tz_utils

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
            return field_key.startswith("#") or field_key.startswith("@") or field_key.startswith("_")\
            or field_key.lower() in SYSTEM_FIELD_NAMES

        def format_name(value):
            if not isinstance(value, basestring):
                value = unicode(value)
            return value.replace("_", " ")

        def render_base_type(key, value):
            if not value: return ""
            return '<dt><i class="icon-info-sign"></i> %s</dt><dd>%s</dd>' % (format_name(key), format_name(value))


        def is_base_type(value):
            return isinstance(value, basestring) or\
                   isinstance(value, date) or\
                   isinstance(value, datetime)

        if not nodevalue or is_hidden_field(nodekey): return ""
        if is_base_type(nodevalue):
            return render_base_type(nodekey, nodevalue)
        else:
            header = '<dt class="nest-head">%s</dt>' % format_name(nodekey)
            # process a dictionary
            if isinstance(nodevalue, types.DictionaryType):
                node_list = []
                for key, value in nodevalue.items() :
                    # recursive call
                    node = render_node(key, value)
                    if node: node_list.append(node)

                if node_list:
                    return '%(header)s<dd class="nest-body"><dl>%(body)s</dl></dd>' %\
                           {"header": header,
                            "body": "".join(node_list)}
                else:
                    return ""
            elif isinstance(nodevalue, types.ListType) or\
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
                    full_list.append("%(header)s<dd><ul>%(body)s</ul></dd>" %\
                                     {"header": header,
                                      "body": "".join(node_list)})
                return "".join(full_list)
            else:
                return render_base_type(nodekey, nodevalue)

    return '<dl class="def-form-data">%s</dl>' % "".join(render_node(key, val) for key, val in form.top_level_tags().items())

@register.simple_tag
def render_form_xml(form):
    return '<pre id="formatted-form-xml" class="prettyprint linenums"><code class="language-xml">%s</code></pre>' % escape(form.get_xml().replace("><", ">\n<"))

@register.simple_tag
def form_inline_display(form_id, timezone=pytz.utc):
    if form_id:
        form = XFormInstance.get(form_id)
        if form:
            return "%s: %s" % (tz_utils.adjust_datetime_to_timezone(form.received_on, pytz.utc.zone, timezone.zone).date(), form.xmlns)
        return "missing form: %s" % form_id
    return "empty form id found"
