from django import template
from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse

from django.contrib.contenttypes.models import ContentType
from types import ListType,TupleType

from organization.models import *

import xformmanager.adapter.querytools as qtools
import organization.utils as utils
from xformmanager.models import *
import time
from datetime import timedelta
import dbanalyzer.dbhelper as dbhelper

xmldate_format= '%Y-%m-%dT%H:%M:%S'
output_format = '%Y-%m-%d %H:%M'
username_datecount_cache = {}

register = template.Library()

@register.simple_tag
def get_daterange_links(view_name, args={}):
    base_link = reverse(view_name,kwargs=args)

    delta_week = timedelta(days=7)
    delta_day= timedelta(days=1)
    delta_month = timedelta(days=30)
    delta_3month = timedelta(days=90)
        
    enddate = datetime.now()    
    
    #datetime.strptime(startdate_str,'%m/%d/%Y')
    ret = ''
    ret += '<div class="daterange_tabs"><ul>'
    ret += '<li><a href="%s">Last Day</a>' % (base_link)
    ret += '<li><a href="%s?startdate=%s&enddate=%s">Last Week</a>' % (base_link, (enddate - delta_week).strftime('%m/%d/%Y'), (enddate).strftime('%m/%d/%Y'))
    ret += '<li><a href="%s?startdate=%s&enddate=%s">Last Month</a>' % (base_link, (enddate - delta_month).strftime('%m/%d/%Y'), enddate.strftime('%m/%d/%Y'))
    ret += '<li><a href="%s?startdate=%s&enddate=%s">Last 3 Months</a>' % (base_link, (enddate - delta_3month).strftime('%m/%d/%Y'), enddate.strftime('%m/%d/%Y'))
    ret += "</ul></div>"
    return ret


@register.simple_tag
def aggregate_section_totals(section_name, results_arr, daily):
    """Hackish function to do a summation of a section in the org_report"""    
    #go through the array and go to the index that my section name is
    startindex = -1
    endindex = -1
    for itemarr in results_arr:
        if itemarr[1] == section_name:
            startindex = results_arr.index(itemarr)
            continue
        
        if startindex >= 0:
            if itemarr[1] != None:
                endindex = results_arr.index(itemarr)
                break
    
    
    summation = []
    section_arr = []
    if endindex == -1:
        section_arr = results_arr[startindex:]
    else:
        section_arr = results_arr[startindex:endindex+1]
        
    for itemarr in section_arr:
        if summation == []:
            summation = summation + itemarr[-1]
        else:
            for i in range(0,len(itemarr[-1])):
                summation[i] += itemarr[-1][i]
                
    ret = ''
    if daily:        
        for item in summation:
            ret += '<td style="background:#99FFFF"><strong>%d</strong></td>' % item
    else:
        sum = 0
        for item in summation:
            sum += item
        ret = "<td>%d</td>" % sum
    return ret
                           
