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
import dbanalyzer.dbhelper as dbhelper

xmldate_format= '%Y-%m-%dT%H:%M:%S'
output_format = '%Y-%m-%d %H:%M'
username_datecount_cache = {}

register = template.Library()



@register.simple_tag
def get_daterange_links():
    base_link = reverse('organization.views.org_report',kwargs={})

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
def get_organization_report(extuser, startdate, enddate):
    """Main tag to get an organization report on counts and such"""    
    
    username_datecount_cache = {}        
    domain = extuser.domain    
    
    ctype = ContentType.objects.get_for_model(domain)
    root_orgs = Edge.objects.all().filter(parent_type=ctype,parent_id=domain.id,relationship__name='is domain root')
    
    if len(root_orgs) == 0:
        return '<h1>Error</h1>'
    root_org = root_orgs[0]
    
    descendents = traversal.getDescendentEdgesForObject(root_org.parent_object)  #if we do domain, we go too high
    
    day_count_hash = {}
    
    totalspan = enddate-startdate    
    
    header_row = '<tr><td class="rowheading"></td>'
    for day in range(0,totalspan.days+1):   
        delta = timedelta(days=day)
        target_date = startdate + delta  
        header_row += '<td class="headercol">%s</td>'% (target_date.strftime('%m/%d/%Y'))
    header_row += '</tr>'    

    
    if len(descendents) > 0:
        ret = '<h4>Domain: ' + str(root_org.parent_object) + '</h4>'
        ret += '<div class="reports"><table class="reporttable">' + header_row + render_edgetree_as_table(descendents,'children', startdate, enddate,0).__str__() + '</table></div>'
        
        username_datecount_cache.clear()
        return ret
    else:
        return '<div class="reports"><h4>No domain configuration found</h4></div>'    

def render_edgetree_as_ul(arr, direction, startdate, enddate):   
    fullret = ''
    
    prior_edgetype = None
    group_edge = False
    
    for edges in arr:
        subitems = ''
        sublist = ''
        edge = None            
        
        if isinstance(edges,ListType):            
            sublist += '\n<ul>'    
            sublist += render_edgetree_as_ul(edges,direction,startdate, enddate)
            sublist += '</ul>'
            sublist += '</ul>'
            
                                        
        else:            
            if edge == None:            
                edge = edges
            if edge.relationship != prior_edgetype:      
                if group_edge:
                    group_edge = False
                    subitems +=  '</ul>'              
                prior_edgetype = edge.relationship
                subitems += '<li>'
                subitems += edge.relationship.description
                subitems +=  '<ul>'
                group_edge = True            
                            
            subitems += '\t<li><div class="reportitem">'
            item_to_render = None
            if direction == 'children':
                subitems += '<a href="%s?content_type=%s&content_id=%s">%s</a>' % (reverse('org_report', kwargs= {}),edge.child_type.id,edge.child_object.id,edge.child_object)
                item_to_render = edge.child_object                         
            else:
                subitems += '<a href="%s?content_type=%s&content_id=%s">%s</a>' % (reverse('org_report', kwargs= {}),edge.parent_type.id,edge.parent_object.id,edge.parent_object)
                item_to_render = edge.parent_object
                
            subitems += '<table>\n\t\t'
            subitems += render_aggregate_countrow(item_to_render, startdate, enddate)
            subitems += '</table></div>'
            subitems += '\t</li>'                        
            subitems += '</li>'    
        
        if direction == 'children':
            fullret += subitems + sublist 
        else:
            fullret += subitems + sublist
    return fullret



def render_edgetree_as_table(arr, direction, startdate, enddate, depth):   
    fullret = ''
    
    prior_edgetype = None
    group_edge = False
    
    for edges in arr:
        subitems = ''
        sublist = ''
        edge = None            
        
        if isinstance(edges,ListType):            
            sublist += '\n<tr>'    
            sublist += render_edgetree_as_table(edges,direction,startdate, enddate, depth + 1)
            sublist += '</tr>\n'
            
                                        
        else:            
            if edge == None:            
                edge = edges
            if edge.relationship.name == "Domain Chart":    #ugly hack.  we need to constrain by the relationship types we want to do
                return fullret
            if edge.relationship != prior_edgetype:      
                if group_edge:
                    group_edge = False
                    #subitems +=  '</tr>'              
                prior_edgetype = edge.relationship
                subitems += '\n<tr><td class="rel_row" style="padding-left:%dpx;">' % (depth * 25)
                subitems += edge.relationship.description
                subitems +=  '</td></tr>\n'
                group_edge = True            
                            
            subitems += '\t<td class="item_row" style="padding-left:%dpx;">' % (depth * 40)
            item_to_render = None
            if direction == 'children':
                #subitems += '<a href="%s?content_type=%s&content_id=%s">%s</a>' % (reverse('org_report', kwargs= {}),edge.child_type.id,edge.child_object.id,edge.child_object)
                subitems += edge.child_object.__str__()
                item_to_render = edge.child_object                         
            else:
                #subitems += '<a href="%s?content_type=%s&content_id=%s">%s</a>' % (reverse('org_report', kwargs= {}),edge.parent_type.id,edge.parent_object.id,edge.parent_object)
                subitems += edge.child_object.__str__()
                item_to_render = edge.parent_object
                
            subitems += '\t</td>'           
            subitems += render_aggregate_countrow(item_to_render, startdate, enddate)                         
            subitems += '</tr>'    
        
        if direction == 'children':
            fullret += subitems + sublist 
        else:
            fullret += subitems + sublist
    username_datecount_cache.clear()
    return fullret



def get_user_allforms_count(domain, username, startdate=None, enddate=None):
    ret  = ''
    totalspan = enddate-startdate    
    day_count_hash = {}
    #print 'get_user_allforms_count'
    for day in range(0,totalspan.days+1):
        delta = timedelta(days=day)
        target_date = startdate + delta
        #print "get_user_allforms_count: %s" % (str(target_date))
        day_count_hash[target_date.strftime('%m/%d/%Y')] = 0
    
    defs = FormDefData.objects.all().filter(uploaded_by__domain=domain)
    
    for fdef in defs:        
        table = fdef.element.table_name        
        helper = dbhelper.DbHelper(table, fdef.form_display_name)
        userdailies = helper.get_filtered_date_count(startdate, enddate,filters={'username': username})                        
        for dat in userdailies:         
            #dt = time.strptime(str(dat[1][0:-4]),xmldate_format)
            #datum = datetime(dt[0],dt[1],dt[2],dt[3],dt[4],dt[5],dt[6])
            #day_count_hash[datum.strftime('%m/%d/%Y')] += int(dat[0])    
            day_count_hash[dat[1]] += int(dat[0])
    
    #print day_count_hash
    return day_count_hash


def render_aggregate_countrow(content_obj, startdate, enddate):
    #report_query = "select '%s', (select TimeEnd from %s where username='%s' order by timeend desc limit 1), (select count(*) from %s where username='%s');"
    usernames_to_filter = []    
    ret  = ''

    totalspan = enddate-startdate    
    master_date_hash = {}
        
    for day in range(0,totalspan.days+1):
        delta = timedelta(days=day)
        target_date = startdate + delta
        master_date_hash[target_date.strftime('%m/%d/%Y')] = 0

    is_supervisor = False
    is_org = False
    is_member = False
    domain = None
    if isinstance(content_obj, Organization):
        is_org = True        
        domain  = content_obj.domain
        (members, supervisors) = utils.get_members_and_supervisors(content_obj)        
        for member in members:
            usernames_to_filter.append(member.username)
        for supervisor in supervisors:
            usernames_to_filter.append(supervisor.username)
    elif isinstance(content_obj, ExtUser):        
        domain  = content_obj.domain
        supervising_orgs = utils.get_supervisor_roles(content_obj)
        usernames_to_filter.append(content_obj.username)
        is_member = True    
        
    
    for user in usernames_to_filter:
        if not username_datecount_cache.has_key(user):
            username_datecount_cache[user] = get_user_allforms_count(domain, user, startdate, enddate)
            
        for target_date in username_datecount_cache[user].keys():
            master_date_hash[target_date] += username_datecount_cache[user][target_date]
        
    #ret = '<tr>'    
    row = ''
    #for date, val in master_date_hash.items():
    for day in range(0,totalspan.days+1):        
        delta = timedelta(days=day)        
        target_date = startdate + delta
        val = master_date_hash[target_date.strftime('%m/%d/%Y')]
        
        #ret += '<td>%s</td>' % (target_date.strftime('%m/%d/%Y'))
        row += '<td>%d</td>' % (val)
        
        
    #ret += '</tr>'
    #ret += "<tr>"
    #ret += row
    #ret += '</tr>'
    
    return row