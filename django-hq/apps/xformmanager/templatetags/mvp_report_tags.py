from django import template
from django.template.loader import render_to_string
from django.core.urlresolvers import reverse


import time

register = template.Library()


@register.simple_tag
def get_monitoring_table(data):    
    context = {}
    context["data"] = data 
    return render_to_string("reports/mvp/monitoring_table.html", context)
    return ''
