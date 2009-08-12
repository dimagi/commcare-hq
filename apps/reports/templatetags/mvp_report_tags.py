from django import template
from django.template.loader import render_to_string
from django.core.urlresolvers import reverse


import time

register = template.Library()


@register.simple_tag
def get_monitoring_table(data):    
    context = {}
    context["data"] = data 
    context["empty_data_holder"] = "<b></b>"
    return render_to_string("custom/shared/monitoring_table.html", context)
    return ''

