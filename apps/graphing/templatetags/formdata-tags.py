from django import template
from django.core.urlresolvers import reverse
from xformmanager.models import *


from django.contrib.contenttypes.models import ContentType
from types import ListType,TupleType

from hq.models import *
import graphing.dbhelper as dbhelper  

import xformmanager.adapter.querytools as qtools


register = template.Library()

import time
#time.mktime(datetime.datetime.now().timetuple())
#where timetuple = (1970, 3, 31, 15, 48, 55, 1, 90, -1)


@register.simple_tag
def get_form_links(domain):
    """Get a link to each form in the system"""
    # this is apparently broken, as of 12/2009.  Leaving here
    # in case it should be revived.
    base_link = reverse('graphing.views.summary_trend',kwargs={})
    
    #<a href="%s?content_type=%s&content_id=%s">%s</a>
    defs = FormDefModel.objects.all().filter(domain=domain)
    ret = ''
    ret += "<ul>"
    ret += '<li><a href="%s">%s</a></li>' % (base_link, "Show all")    
    for fdef in defs:                
        ret += '<li><a href="%s?formdef_id=%s">%s</a></li>' % (base_link, fdef.id,fdef.form_display_name)        
    
    ret+="</ul>"
    return ret
