from django import template

register = template.Library()


@register.simple_tag
def ajax_filter_url(domain, report, filter):
    return filter.url_generator(domain, report, filter)
