from django import template

register = template.Library()


@register.inclusion_tag('hqstyle/forms/basic_errors.html')
def bootstrap_form_errors(form):
    return {'form': form}
