from __future__ import absolute_import
from django import template
from django.forms import CheckboxInput

register = template.Library()


@register.filter(name='is_checkbox')
def is_checkbox(field):
    return isinstance(field.field.widget, CheckboxInput)
