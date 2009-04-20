from django import template

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
from datetime import timedelta
import dbanalyzer.dbhelper as dbhelper
from organization.models import *
register = template.Library()

import time

xmldate_format= '%Y-%m-%dT%H:%M:%S'
output_format = '%Y-%m-%d %H:%M'

@register.simple_tag
def get_daterange_links():
    base_link = reverse('organization.views.dashboard',kwargs={})

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
def get_dashboard_activity(user, startdate=None, enddate=None):    
    report_query = "select '%s', (select TimeEnd from %s where username='%s' order by timeend desc limit 1), (select count(*) from %s where username='%s');"
    ret  = ''   
    extuser = User.objects.get(id=user.id)
    
    defs = FormDefData.objects.all()
    ret += '<ul class="nobullets">'
    for fdef in defs:                
        ret += "<li><h2>%s</h2>" % (fdef.form_display_name)
        ret += ""
        
        table = fdef.element.table_name
        
        helper = dbhelper.DbHelper(table, fdef.form_display_name)
        ret += '<table class="sofT"><tr><td class="helpHed">Username</td><td class="helpHed">Last Submit</td><td class="helpHed">Total Count</td></tr>'
        
        
        #let's get the usernames
        usernames_to_filter = helper.get_uniques_for_column('username', startdate, enddate)
        
        for user in usernames_to_filter:
            ret += "<tr>"
            query = report_query % (user,table,user,table,user)
            #print query
            
            userdata = qtools.raw_query(query)
            for dat in userdata[0]:
                i = 0
                for f in dat:
                    if i == 1 and f != None:
                        ret += "<td>%s</td>" % time.strftime(output_format, time.strptime(str(f)[0:-4],xmldate_format))
                        #ret += "<td>%s</td>" % str(f)
                    else:
                        ret += "<td>%s</td>" % str(f)
                    i=i+1
            ret += "</tr>"  
        ret += "</table></li>"
    ret += "</ul>"  
    return ret



@register.simple_tag
def get_dashboard_user_counts(user, startdate=None, enddate=None):
    ret  = ''
    
    username_to_count_hash = {}
    
    #todo:  query the global meta tables to get all the users
    #and/or query the ExtUser table to get all the registered users.
    totalspan = enddate-startdate    
    report_hash = {}
    extuser = ExtUser.objects.get(id=user.id)
        
    for day in range(0,totalspan.days+1):
        delta = timedelta(days=day)
        target_date = startdate + delta
        #print target_date.strftime('%m/%d/%Y')
        report_hash[target_date.strftime('%m/%d/%Y')] = {}
    
    #for now, we're going to get all the users in the system by querying the actual tables for usernames
    defs = FormDefData.objects.all().filter(uploaded_by__domain=extuser.domain)
    
    for fdef in defs:        
        table = fdef.element.table_name
        
        helper = dbhelper.DbHelper(table, fdef.form_display_name) 
        #let's get the usernames
        usernames_to_filter = helper.get_uniques_for_column('username', None, None)           
                
        for user in usernames_to_filter:            
            if not username_to_count_hash.has_key(user):
                username_to_count_hash[user] = {}                        
            
            userdailies = helper.get_filtered_date_count(startdate, enddate,filters={'username': user})                        
            for dat in userdailies:                
                username_to_count_hash[user][dat[1]] = int(dat[0])

    
    ret += '<table class="sofT"><tr><td class="helpHed">Date</td>'
    for user in username_to_count_hash.keys():
        ret += '<td  class="helpHed">%s</td>' % (user)
        for datestr in username_to_count_hash[user].keys():
            #dt = time.strptime(str(datestr[0:-4]),xmldate_format)
            #datum = datetime(dt[0],dt[1],dt[2],dt[3],dt[4],dt[5],dt[6])
            #date = datum.strftime('%m/%d/%Y')              
            if not report_hash[datestr].has_key(user):
                report_hash[datestr][user]=username_to_count_hash[user][datestr]
        
    ret += "</tr>\n"
    
    
    #for date in report_hash.keys():
    for day in range(0,totalspan.days+1):
        delta = timedelta(days=day)
        target_date = startdate + delta
        date = target_date.strftime('%m/%d/%Y')
        ret += "<tr>"
        ret += "<td>%s</td>" % (date)
        for user in username_to_count_hash.keys():
            val = 0
            if report_hash[date].has_key(user):
                val = report_hash[date][user]
            ret += "<td>%d</td>" % (val)
        ret += "</tr>\n\n"
    ret += "</table>"
    username_to_count_hash.clear()
    return ret