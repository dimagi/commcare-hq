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

pretty_table_names = {'x_http__www_commcare_org_mvp_safe_motherhood_close_v0_1' : "Safe Motherhood Closure", 
                      'x_http__www_commcare_org_mvp_safe_motherhood_followup_v0_1': 'Safe Motherhood Followup',
                      'x_http__www_commcare_org_mvp_safe_motherhood_registration_v0_1' : "Safe Motherhood Registration",
                      'x_http__www_commcare_org_mvp_safe_motherhood_referral_v0_1': "Safe Motherhood Referral"}


@register.simple_tag
def get_aggregate_formcounts_for_obj(content_obj):
    
    # % (username,table,username,table,username)
    report_query = "select '%s', (select TimeEnd from %s where username='%s' order by timeend desc limit 1), (select count(*) from %s where username='%s');"
    
    
    
    #if an organization, just query all its forms    
    # if it's a group, make a cluster of all the users he/she supervises    
    # ifit's a user, just do counts off its userid from meta
    
    #<Meta>!!!!
    #formname
    #formversion
    #deviceid
    #timestart
    #timend
    #username
    #uid
    #chw_id
    #for hacking now, we are going to iterate over all the formdefs
    
    usernames_to_filter = []    
    ret  = ''
    
    if content_obj is None:
        ret += "<h2>All Data</h2>"
        #allusers = qtools.raw_query(all_user_query)
        users_rawlist = ExtUser.objects.all().values_list('username')
        for usertuple in users_rawlist:
            usernames_to_filter.append(usertuple[0])
                
    elif isinstance(content_obj, Organization):
        ret += "<h2>Data for %s</h2>" % (content_obj.name)
        (members, supervisors) = utils.get_members_and_supervisors(content_obj)
        
        for member in members:
            usernames_to_filter.append(member.username)
        for supervisor in supervisors:
            usernames_to_filter.append(supervisor.username)
    elif isinstance(content_obj, ExtUser):
        ret += "<h2>Data for User %s</h2>" % (content_obj.username)
        supervising_orgs = utils.get_supervisor_roles(content_obj)
        if len(supervising_orgs) > 0:
            for org in supervising_orgs:
                (mem,sup) = utils.get_members_and_supervisors(org)
                for m in mem:
                    if usernames_to_filter.count(m.username) == 0:
                       usernames_to_filter.append(m.username)
        else:
            usernames_to_filter.append(content_obj.username)
        
        
            
         

    
    
    defs = FormDefData.objects.all()
    ret += '<ul>'
    for fdef in defs:                
        ret += "<li><h2>%s</h2>" % (pretty_table_names[fdef.element.table_name])
        ret += ""
        
        table = fdef.element.table_name        
        ret += '<table class="sofT"><tr><td class="helpHed">Username</td><td class="helpHed">Last Submit</td><td class="helpHed">Total Count</td></tr>'
        #print usernames_to_filter
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