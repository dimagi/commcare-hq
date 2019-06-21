from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django import template
from django.urls import reverse
from datetime import datetime, timedelta
from corehq.const import SERVER_DATETIME_FORMAT_NO_SEC
from six.moves import range

xmldate_format= '%Y-%m-%dT%H:%M:%S'
output_format = SERVER_DATETIME_FORMAT_NO_SEC
username_datecount_cache = {}

register = template.Library()


@register.simple_tag
def get_daterange_links(view_name, args={}):
    base_link = reverse(view_name, kwargs=args)
    return get_daterange_links_raw(base_link, args)


@register.simple_tag
def get_daterange_links_raw(base_link, args={}):
    delta_week = timedelta(days=7)
    delta_day= timedelta(days=1)
    delta_month = timedelta(days=30)
    delta_3month = timedelta(days=90)
    
    enddate = datetime.utcnow()
    yesterday = enddate - delta_day
    #datetime.strptime(startdate_str,'%m/%d/%Y')
    ret = '\n'
    ret += '<div class="daterange_tabs"><ul>'
    ret += '<li><a href="%s?startdate=%s&enddate=%s">Today</a>' % (base_link, enddate.strftime('%m/%d/%Y'), enddate.strftime('%m/%d/%Y'))
    ret += '<li><a href="%s?startdate=%s&enddate=%s">Yesterday</a>' % (base_link, yesterday.strftime('%m/%d/%Y'), yesterday.strftime('%m/%d/%Y'))
    ret += '<li><a href="%s?startdate=%s&enddate=%s">Last Week</a>' % (base_link, (enddate - delta_week).strftime('%m/%d/%Y'), (enddate).strftime('%m/%d/%Y'))
    ret += '<li><a href="%s?startdate=%s&enddate=%s">Last Month</a>' % (base_link, (enddate - delta_month).strftime('%m/%d/%Y'), enddate.strftime('%m/%d/%Y'))
    ret += '<li><a href="%s?startdate=%s&enddate=%s">Last 3 Months</a>' % (base_link, (enddate - delta_3month).strftime('%m/%d/%Y'), enddate.strftime('%m/%d/%Y'))
    ret += "</ul></div>"
    return ret


@register.simple_tag
def get_daterange_links_basic(base_link, days=[0, 7, 30, 90], args={}):
    '''Allows you to pass in a list of day counts representing how 
       far to go back for each link. For known links it will generate
       a pretty string to display the time, otherwise it will say
       "last n days"''' 
    #base_link = reverse(view_name,kwargs=args)
    end_date = datetime.utcnow()
    ret = ''
    ret += '<div class="daterange_tabs"><ul>\n'
    for num_days in days:
        ret += _get_formatted_date_link(base_link, end_date, num_days) + "\n"
    ret += "</ul></div>"
    return ret


def _get_formatted_date_link(base_link, end_date, num_days):
    return '<li><a href="%s?startdate=%s&enddate=%s">%s</a></li>' % (base_link, 
                                                                (end_date - timedelta(days=num_days)).strftime('%m/%d/%Y'), 
                                                                end_date.strftime('%m/%d/%Y'), 
                                                                _get_time_interval_display(num_days))


def _get_time_interval_display(num_days):
    '''Gets a display string representing the interval.'''
    if num_days == 0:
        return "Today"
    elif num_days == 7:
        return "Last Week"
    elif num_days == 30:
        return "Last Month"
    elif num_days == 365:
        return "Last Year"
    elif num_days % 365 == 0:
        yrs = num_days // 365
        return "Last %s Years" % yrs
    elif num_days % 30 == 0:
        months = num_days // 30
        return "Last %s Months" % months
    else:
        return "Last %s Days" % num_days
    

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
            for i in range(0, len(itemarr[-1])):
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
