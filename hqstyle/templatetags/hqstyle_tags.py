from django import template

register = template.Library()

@register.inclusion_tag('hqstyle/forms/basic_fieldset.html')
def bootstrap_fieldset(form, fieldset_name=''):
    return {'form':form, 'legend':fieldset_name}

@register.inclusion_tag('hqstyle/forms/basic_errors.html')
def bootstrap_form_errors(form):
    return {'form':form}
