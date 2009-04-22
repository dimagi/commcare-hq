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
def get_daterange_links(view_name):
    base_link = reverse(view_name,kwargs={})

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


#===============================================================================
# @register.simple_tag
# def get_domain_report(domain, startdate, enddate, render_html=True):
#    """Main tag to get an organization report on counts and such"""    
#    
#    username_datecount_cache = {}        
#        
#    ctype = ContentType.objects.get_for_model(domain)
#    root_orgs = Edge.objects.all().filter(parent_type=ctype,parent_id=domain.id,relationship__name='is domain root')
#    
#    if len(root_orgs) == 0:
#        return '<h1>Error</h1>'
#    root_org = root_orgs[0]
#    
#    descendents = traversal.getDescendentEdgesForObject(root_org.parent_object)  #if we do domain, we go too high
#    
#    day_count_hash = {}
#    
#    
#    if render_html:
#        header_row = '<tr><td class="rowheading"></td>'
#    else:
#        header_row = ''
#    totalspan = enddate-startdate    
#    for day in range(0,totalspan.days+1):   
#        delta = timedelta(days=day)
#        target_date = startdate + delta
#        if render_html:  
#            header_row += '<td class="headercol">%s</td>'% (target_date.strftime('%m/%d/%Y'))
#        else:
#            header_row = '\t%s' % (target_date.strftime('%m/%d/%Y'))
#    
#    if render_html:
#        header_row += '</tr>'
#    else:
#        header_row += '\n'
#        
#    if len(descendents) > 0:
#        ret = ''
#        
#        if render_html:
#            ret += '<h4>Domain: ' + str(root_org.parent_object) + '</h4><div class="reports"><table class="reporttable">'
#        
#        ret += header_row + render_edgetree_as_table(descendents,'children', startdate, enddate,0, render_html=render_html).__str__()
#        
#        if render_html:
#            ret += '</table></div>'
#        
#        username_datecount_cache.clear()
#        return ret
#    else:
#        return '<div class="reports"><h4>No domain configuration found</h4></div>'    
#===============================================================================

#def render_edgetree_as_ul(arr, direction, startdate, enddate):   
#    fullret = ''
#    
#    prior_edgetype = None
#    group_edge = False
#    
#    for edges in arr:
#        subitems = ''
#        sublist = ''
#        edge = None            
#        
#        if isinstance(edges,ListType):            
#            sublist += '\n<ul>'    
#            sublist += render_edgetree_as_ul(edges,direction,startdate, enddate)
#            sublist += '</ul>'
#            sublist += '</ul>'
#            
#                                        
#        else:            
#            if edge == None:            
#                edge = edges
#            if edge.relationship != prior_edgetype:      
#                if group_edge:
#                    group_edge = False
#                    subitems +=  '</ul>'              
#                prior_edgetype = edge.relationship
#                subitems += '<li>'
#                subitems += edge.relationship.description
#                subitems +=  '<ul>'
#                group_edge = True            
#                            
#            subitems += '\t<li><div class="reportitem">'
#            item_to_render = None
#            if direction == 'children':
#                subitems += '<a href="%s?content_type=%s&content_id=%s">%s</a>' % (reverse('org_report', kwargs= {}),edge.child_type.id,edge.child_object.id,edge.child_object)
#                item_to_render = edge.child_object                         
#            else:
#                subitems += '<a href="%s?content_type=%s&content_id=%s">%s</a>' % (reverse('org_report', kwargs= {}),edge.parent_type.id,edge.parent_object.id,edge.parent_object)
#                item_to_render = edge.parent_object
#                
#            subitems += '<table>\n\t\t'
#            subitems += render_aggregate_countrow(item_to_render, startdate, enddate)
#            subitems += '</table></div>'
#            subitems += '\t</li>'                        
#            subitems += '</li>'    
#        
#        if direction == 'children':
#            fullret += subitems + sublist 
#        else:
#            fullret += subitems + sublist
#    return fullret



#===============================================================================
# 
# def render_edgetree_as_table(arr, direction, startdate, enddate, depth, render_html=True):   
#    fullret = ''
#    
#    prior_edgetype = None
#    group_edge = False
#    
#    for edges in arr:
#        subitems = ''
#        sublist = ''
#        edge = None            
#        
#        if isinstance(edges,ListType):
#            if render_html:            
#                sublist += '\n<tr>'
#            else:
#                sublist += '\n'    
#            sublist += render_edgetree_as_table(edges,direction,startdate, enddate, depth + 1, render_html=render_html)
#            
#            if render_html:
#                sublist += '</tr>\n'
#            else:
#                sublist += '\n'
#                                        
#        else:            
#            if edge == None:            
#                edge = edges
#            if edge.relationship.name == "Domain Chart":    #ugly hack.  we need to constrain by the relationship types we want to do
#                return fullret
#            if edge.relationship != prior_edgetype:      
#                if group_edge:
#                    group_edge = False
#                    #subitems +=  '</tr>'              
#                prior_edgetype = edge.relationship
#                if render_html:
#                    subitems += '\n<tr><td class="rel_row" style="padding-left:%dpx;">' % (depth * 25)
#                else:
#                    subitems += '\t'
#                subitems += edge.relationship.description
#                if render_html:               
#                    subitems +=  '</td></tr>\n'
#                else:
#                    subitems += '\n'
#                group_edge = True            
# 
# 
#            if render_html:
#                subitems += '\t<td class="item_row" style="padding-left:%dpx;">' % (depth * 40)
#            else:
#                subitems += '\t'
#            item_to_render = None
#            if direction == 'children':
#                #subitems += '<a href="%s?content_type=%s&content_id=%s">%s</a>' % (reverse('org_report', kwargs= {}),edge.child_type.id,edge.child_object.id,edge.child_object)
#                subitems += edge.child_object.__str__()
#                item_to_render = edge.child_object                         
#            else:
#                #subitems += '<a href="%s?content_type=%s&content_id=%s">%s</a>' % (reverse('org_report', kwargs= {}),edge.parent_type.id,edge.parent_object.id,edge.parent_object)
#                subitems += edge.child_object.__str__()
#                item_to_render = edge.parent_object
#                
#            if render_html:
#                subitems += '\t</td>'
#            else:
#                subitems += '\t'           
#            subitems += render_aggregate_countrow(item_to_render, startdate, enddate, render_html=render_html)                         
#            if render_html:
#                subitems += '</tr>'                
#        
#        if direction == 'children':
#            fullret += subitems + sublist 
#        else:
#            fullret += subitems + sublist
#    username_datecount_cache.clear()
#    return fullret
#===============================================================================





#===============================================================================
# 
# 
# def render_aggregate_countrow(content_obj, startdate, enddate, render_html=True):
#    rowarr = get_aggregate_count(content_obj, startdate, enddate)
#    
#    ret = ''
#    for val in rowarr:
#        if render_html:
#            ret += '<td>%d</td>' % (val)
#        else:
#            ret += '\t%d' % (val)
#    return ret
#===============================================================================

##old version, new version simplifies calls
#def render_aggregate_countrow(content_obj, startdate, enddate, render_html=True):
#    #report_query = "select '%s', (select TimeEnd from %s where username='%s' order by timeend desc limit 1), (select count(*) from %s where username='%s');"
#    usernames_to_filter = []    
#    ret  = ''
#
#    totalspan = enddate-startdate    
#    master_date_hash = {}
#        
#    for day in range(0,totalspan.days+1):
#        delta = timedelta(days=day)
#        target_date = startdate + delta
#        master_date_hash[target_date.strftime('%m/%d/%Y')] = 0
#
#    is_supervisor = False
#    is_org = False
#    is_member = False
#    domain = None
#    if isinstance(content_obj, Organization):
#        is_org = True        
#        domain  = content_obj.domain
#        (members, supervisors) = utils.get_members_and_supervisors(content_obj)        
#        for member in members:
#            usernames_to_filter.append(member.username)
#        for supervisor in supervisors:
#            usernames_to_filter.append(supervisor.username)
#    elif isinstance(content_obj, ExtUser):        
#        domain  = content_obj.domain
#        supervising_orgs = utils.get_supervisor_roles(content_obj)
#        usernames_to_filter.append(content_obj.username)
#        is_member = True    
#        
#    
#    for user in usernames_to_filter:
#        if not username_datecount_cache.has_key(user):
#            username_datecount_cache[user] = get_user_allforms_count(domain, user, startdate, enddate)
#            
#        for target_date in username_datecount_cache[user].keys():
#            master_date_hash[target_date] += username_datecount_cache[user][target_date]
#        
#    #ret = '<tr>'    
#    row = ''
#    
#    #for date, val in master_date_hash.items():
#    for day in range(0,totalspan.days+1):        
#        delta = timedelta(days=day)        
#        target_date = startdate + delta
#        val = master_date_hash[target_date.strftime('%m/%d/%Y')]
#        
#        #ret += '<td>%s</td>' % (target_date.strftime('%m/%d/%Y'))
#        if render_html:
#            row += '<td>%d</td>' % (val)
#        else:
#            row += '\t%d' % (val)
#        
#        
#    #ret += '</tr>'
#    #ret += "<tr>"
#    #ret += row
#    #ret += '</tr>'
#    
#    return row