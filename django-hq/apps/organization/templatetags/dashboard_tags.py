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
    defs = FormDefModel.objects.all().filter(uploaded_by__domain=extuser.domain)
    
    for fdef in defs:        
        table = fdef.element.table_name
        helper = dbhelper.DbHelper(table, fdef.form_display_name) 
        #let's get the usernames
        usernames_to_filter = helper.get_uniques_for_column('meta_username', None, None)           
        for user in usernames_to_filter:            
            if not username_to_count_hash.has_key(user):
                username_to_count_hash[user] = {}                        
            
            userdailies = helper.get_filtered_date_count(startdate, enddate,filters={'meta_username': user})   
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