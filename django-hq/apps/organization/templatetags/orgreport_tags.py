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

#deprecated

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
        users_rawlist = ExtUser.objects.all().values_list('meta_username')
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
 
    defs = FormDefModel.objects.all()
    ret += '<ul>'
    for fdef in defs:                
        ret += "<li><h2>%s</h2>" % (fdef.form_display_name)
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


def render_aggregate_countrow(content_obj):
    report_query = "select '%s', (select TimeEnd from %s where username='%s' order by timeend desc limit 1), (select count(*) from %s where username='%s');"
    usernames_to_filter = []    
    ret  = ''

    is_supervisor = False
    is_org = False
    is_member = False
                
    if isinstance(content_obj, Organization):
        is_org = True        
        (members, supervisors) = utils.get_members_and_supervisors(content_obj)        
        for member in members:
            usernames_to_filter.append(member.username)
        for supervisor in supervisors:
            usernames_to_filter.append(supervisor.username)
    elif isinstance(content_obj, ExtUser):        
        supervising_orgs = utils.get_supervisor_roles(content_obj)
        usernames_to_filter.append(content_obj.username)
        
#        if len(supervising_orgs) > 0:
#            is_supervisor = True
#            for org in supervising_orgs:
#                (mem,sup) = utils.get_members_and_supervisors(org)
#                for m in mem:
#                    if usernames_to_filter.count(m.username) == 0:
#                       usernames_to_filter.append(m.username)
#        else:
#            is_member = True
#            usernames_to_filter.append(content_obj.username)
 
    defs = FormDefModel.objects.all()
    description = ''
    last_submit = datetime.min
    count = 0    
    for fdef in defs:    
        table = fdef.element.table_name        
        for user in usernames_to_filter:            
            query = report_query % (user,table,user,table,user)
            userdata = qtools.raw_query(query)
            for dat in userdata[0]:                
                if dat[1] != None:
                    reptime = time.strptime(str(dat[1])[0:-4],xmldate_format)
                    if datetime(reptime[0],reptime[1],reptime[2],reptime[3],reptime[4],reptime[5],reptime[6]) > last_submit:
                        last_submit = datetime(reptime[0],reptime[1],reptime[2],reptime[3],reptime[4],reptime[5],reptime[6])  
                count += dat[-1]
    
    ret += '<tr>'
#    if is_supervisor:
#        ret += '<td>%s</td>' % ("Supervisor's Report")
#    elif is_member:
#        ret += '<td>%s</td>' % ("Member Report:")
#    elif is_org:
#        ret += '<td>%s</td>' % ("Organization Totals")
    ret += '<td>%s</td>' % (content_obj)
    
    ret += '<td>%s</td>' % (time.strftime(output_format,last_submit.timetuple()))
    ret += '<td>%s</td>' % (count)   
    ret += '</tr>'    
    if is_org:
        ret += render_blankrow()
    return ret


def flatten(lst):
    for elem in lst:
        if isinstance(elem,ListType):    
            for i in flatten(elem):
                yield i
        else:
            yield elem

def render_blankrow():
    return '<tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>'

@register.simple_tag
def render_hierarchy_report(domain):    
    ctype = ContentType.objects.get_for_model(domain)
    root_orgs = Edge.objects.all().filter(parent_type=ctype,parent_id=domain.id,relationship__name='is domain root')
    if len(root_orgs) == 0:
        return '<h1>Error</h1>'
    root_org = root_orgs[0].child_object

    
    edgetree = traversal.getDescendentEdgesForObject(root_org)    
    fullret = ''
    
    prior_edgetype = None
    group_edge = False
    
    edgelist = list(flatten(edgetree))
    report_hierarchy = []
    priorparent = None
    relprior = None
    fullret += '<div class="reportable">'
#    fullret += "<h4>Aggregated Counts</h4>"
    fullret += '<table>'
    fullret += '<tr><td>Report</td><td>Last Submit</td><td>Count</td></tr>'
    root = edgelist[0].parent_object
    for edge in edgelist:
        if edge.parent_object == root:
            
            continue
        parent, relationship, child = edge.triple
        
        if relprior != relationship:
            if relprior != None:
                fullret += render_blankrow()
                pass
            relprior = relationship      
       
        
        if parent != priorparent:
            fullret += render_aggregate_countrow(parent)        
            fullret += render_aggregate_countrow(child)
            #report_hierarchy.append(parent)
            #report_hierarchy.append('space')            
            priorparent = parent        
            
            if isinstance(child, Organization):
                #fullret += render_blankrow()
                pass
        else:
            
            fullret += render_aggregate_countrow(child)
            
            if isinstance(child, Organization):
#                fullret += render_blankrow()
                pass
            
        
        
        
  
                
    fullret += "</table></div>"
    return fullret




