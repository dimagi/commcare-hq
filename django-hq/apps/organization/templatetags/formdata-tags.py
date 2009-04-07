from django import template
from django.core.urlresolvers import reverse
from xformmanager.models import *


from modelrelationship.models import *
from django.contrib.contenttypes.models import ContentType
from types import ListType,TupleType

import modelrelationship.traversal as traversal
from modelrelationship.models import *

from organization.models import *
import djflot.dbhelper as dbhelper  

import xformmanager.adapter.querytools as qtools


register = template.Library()

import time
#time.mktime(datetime.datetime.now().timetuple())
#where timetuple = (1970, 3, 31, 15, 48, 55, 1, 90, -1)


@register.simple_tag
def get_form_links(extuser):
    #(reverse('org_manager', kwargs= {}),edge.child_type.id,edge.child_object.id,edge.child_object)
    base_link = reverse('organization.views.summary_trend',kwargs={})
    #<a href="%s?content_type=%s&content_id=%s">%s</a>
    
    defs = FormDefData.objects.all()
    ret = ''
    ret += "<ul>"
    ret += '<li><a href="%s">%s</a></li>' % (base_link, "Show all")    
    for fdef in defs:                
        ret += '<li><a href="%s?formdef_id=%s">%s</a></li>' % (base_link, fdef.id,fdef.form_display_name)        
    
    ret+="</ul>"
    return ret
