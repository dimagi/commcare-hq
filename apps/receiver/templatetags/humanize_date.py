from django import template
from django.template.defaultfilters import stringfilter


register = template.Library()

@register.filter(name='human_date')
@stringfilter
def human_date(timesince):
    return timesince.split(',')[0]
