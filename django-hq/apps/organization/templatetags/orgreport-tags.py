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




@register.simple_tag
def get_aggregate_formcounts_for_obj(content_obj):
    
    # % (username,table,username,table,username)
    report_query = "select '%s', (select TimeEnd from %s where username='%s' order by timeend desc limit 1), (select count(*) from %s where username='%s');"
    
    all_user_query = "select distinct username from %s"
    
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
        allusers = qtools.raw_query(all_user_query)
        for row in allusers:
            for field in row:
                usernames_to_filter.append(field)
                
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
        ret += "<li>%s</li>" % (fdef.element.table_name)
        ret += "<ul><li>"
        
        table = fdef.element.table_name
        ret += "<h3>Table: %s</h3>" % (table)
        ret += "<table><tr><td>Username</td><td>Last Submit</td><td>Total Count</td></tr>"
        #print usernames_to_filter
        for user in usernames_to_filter:
            ret += "<tr>"
            query = report_query % (user,table,user,table,user)
            #print query
            
            userdata = qtools.raw_query(query)
            for dat in userdata[0]:
                for f in dat:
                    ret += "<td>%s</td>" % str(f)
            ret += "</tr>"  
        ret += "</table></ul></li>"
    ret += "</ul>"  
    return ret