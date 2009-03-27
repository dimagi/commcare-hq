from django import template
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from modelrelationship.models import *

@register.simple_tag
def get_all_edgetypes_for_content(contenttype):    
    return ''


@register.simple_tag
def get_parent_edges_for_object(content_object):    
    return ''


@register.simple_tag
def get_child_edges_for_object(content_object):    
    return ''


@register.simple_tag
def get_parent_edgetypes_for_content(contenttype):    
    return ''

@register.simple_tag
def get_child_edgetypes_for_content(contenttype):    
    return ''