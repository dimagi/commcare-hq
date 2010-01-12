from django import template
from xformmanager.models import FormDataPointer

register = template.Library()

@register.simple_tag
def form_data_lookup(column, form):
    '''Lookup the column in the form.  If it is found render it.
       If not return some default thing.'''
    try:
        field = column.fields.get(form=form)
        return field.column_name
    except FormDataPointer.DoesNotExist:
        return "N/A"
    

