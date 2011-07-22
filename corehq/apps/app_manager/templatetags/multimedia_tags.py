from django import template
import json
from corehq.apps.app_manager.templatetags.xforms_extras import trans

register = template.Library()

@register.simple_tag
def render_mm_node(filename, type, modformrefs):
    template = "<li class='%(type)sfile jrfile opener' data-module-count='%(len)s' data-formdata='%(data)s'>%(filename)s</li>"
    
    displaydata = [{"display": "%s: %s" % (trans(m.name, include_lang=False), 
                                           trans(f.name, include_lang=False)),
                    "module": m.id, "form": f.id} for m, f in modformrefs]
    return template % {"filename": filename, "type": type, 
                       "len": len(modformrefs),
                       "data": json.dumps(displaydata)}

