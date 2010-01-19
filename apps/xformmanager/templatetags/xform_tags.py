from django import template
from xformmanager.models import FormDataPointer

register = template.Library()

NOT_SET = "-- not set --"

@register.simple_tag
def form_data_lookup(column, form, editing=False):
    '''Lookup the column in the form.  If it is found render it.
       If not return some default thing saying it's not set.  
       If <editing> is set to true this will return a list of 
       choices based on the available columns in the form.'''
    try:
        field = column.fields.get(form=form)
        value = field.column_name
    except FormDataPointer.DoesNotExist:
        value = NOT_SET
    if not editing:
        return value
    else:
        # TODO: this is lots of querying, so look into optimizing /
        # caching as soon as this starts to get slow
        choices = [col_name for col_name in \
                   FormDataPointer.objects.filter \
                        (form=form, data_type=column.data_type)\
                    .values_list('column_name', flat=True)]
        choices.insert(0, NOT_SET)
        select_name = "select_%s_%s" % (form.id, column.name)
        # something tells me this really doesn't belong on a single line
        expanded_choices = \
            ['<option value="%(choice)s" %(selected)s>%(choice)s</option>' %\
             {"choice": choice, "selected": ('selected="selected"' if value == choice else "")}\
             for choice in choices]
        to_return = '<select name="%s">%s</select>' % (select_name, "".join(expanded_choices))
        return to_return 
        
                                             
            
        
        
        

