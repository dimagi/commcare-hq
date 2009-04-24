from django import template
from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse

from modelrelationship.models import *
from django.contrib.contenttypes.models import ContentType
from types import ListType,TupleType

import modelrelationship.traversal as traversal
from modelrelationship.models import *

from organization.models import *

import xformmanager.adapter.querytools as qtools
import organization.utils as utils
from xformmanager.models import *
import time
from datetime import timedelta


xmldate_format= '%Y-%m-%dT%H:%M:%S'
output_format = '%Y-%m-%d %H:%M'


register = template.Library()

#deprecated

@register.simple_tag
def get_aggregated_reports(domain):
    return ''
    ctype = ContentType.objects.get_for_model(domain)
    root_orgs = Edge.objects.all().filter(parent_type=ctype,parent_id=domain.id,relationship__name='is domain root')
    
    if len(root_orgs) == 0:
        return '<h1>Error</h1>'
    root_org = root_orgs[0]    
    
    count = qtools.get_scalar("select count(*) from x_http__www_commcare_org_mvp_registration1_1_xml")    
    rows, cols = qtools.raw_query("select id, formname, formversion, deviceid, timestart, timeend, username from x_http__www_commcare_org_mvp_registration1_1_xml")
    ret = ''
    ret += '<h2>Total</h2>'
    ret += '<p>%s</p>' % (count)
    ret += '<table><tr>'
    for col in cols:
        ret += '<td>%s</td>' % (col)
    ret += "</tr>"
    for row in rows:
        ret += "<tr>"        
        for field in row:
            ret += '<td>%s</td>' % (str(field))        
        ret += "<tr>"
    ret += '</table>'       
    return ret
    
    #x_http__www_commcare_org_mvp_registration1_1_xml
        
    


