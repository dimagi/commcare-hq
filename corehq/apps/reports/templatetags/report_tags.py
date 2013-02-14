from django import template
from corehq.apps.reports.dispatcher import ReportDispatcher
from dimagi.utils.modules import to_function

register = template.Library()

@register.filter
def dict_lookup(dict, key):
    '''Get an item from a dictionary.'''
    return dict.get(key)
    
@register.filter
def array_lookup(array, index):
    '''Get an item from an array.'''
    if index < len(array):
        return array[index]
    
@register.filter
def attribute_lookup(obj, attr):
    '''Get an attribute from an object.'''
    if (hasattr(obj, attr)):
        return getattr(obj, attr)

@register.simple_tag(takes_context=True)
def report_list(context, dispatcher):
    """
        This requires a valid ReportDispatcher subclass or path.to.ReportDispatcherSubclass
        to generate a Report List.
    """
    if isinstance(dispatcher, basestring):
        dispatcher = to_function(dispatcher)

    return dispatcher.report_navigation_list(context)
