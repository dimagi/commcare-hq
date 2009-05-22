from django import template
from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse

from modelrelationship.models import *
from django.contrib.contenttypes.models import ContentType
from types import ListType,TupleType

import modelrelationship.traversal as traversal
from modelrelationship.models import *

from xformmanager.models import *
import xformmanager.adapter.querytools as qtools
from organization.models import *
import organization.utils as utils

register = template.Library()

import time

xmldate_format= '%Y-%m-%dT%H:%M:%S'
output_format = '%Y-%m-%d %H:%M'

@register.simple_tag
def get_info_block():    
#    ret = '<div class="buildinfoblock">'
#    ret += '<p>Build: %s | ' % (settings.CCHQ_BUILD_INFO)
#    ret += 'Date: %s | ' % settings.CCHQ_BUILD_DATE
#    ret += 'Name: %s' % settings.DATABASE_NAME
#    ret += "</div>"
    #return ret
    return ''
