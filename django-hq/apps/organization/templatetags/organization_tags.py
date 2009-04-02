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


xmldate_format= '%Y-%m-%dT%H:%M:%S'
output_format = '%Y-%m-%d %H:%M'


register = template.Library()

def render_edgetree_as_ul(arr, direction):   
    fullret = ''
    
    prior_edgetype = None
    group_edge = False
    
    for edges in arr:
        subitems = ''
        sublist = ''
        edge = None            
        
        if isinstance(edges,ListType):            
            sublist += '\n<ul>'    
            sublist += render_edgetree_as_ul(edges,direction)
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
                subitems += '<a href="%s?content_type=%s&content_id=%s">%s</a>' % (reverse('org_manager', kwargs= {}),edge.child_type.id,edge.child_object.id,edge.child_object)
                item_to_render = edge.child_object                         
            else:
                subitems += '<a href="%s?content_type=%s&content_id=%s">%s</a>' % (reverse('org_manager', kwargs= {}),edge.parent_type.id,edge.parent_object.id,edge.parent_object)
                item_to_render = edge.parent_object
                
            subitems += '<table>\n\t\t'
            subitems += render_aggregate_countrow(item_to_render)
            subitems += '</table></div>'
            subitems += '\t</li>'                        
            subitems += '</li>'    
        
        if direction == 'children':
            fullret += subitems + sublist 
        else:
            fullret += subitems + sublist
    return fullret

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
        if len(supervising_orgs) > 0:
            is_supervisor = True
            for org in supervising_orgs:
                (mem,sup) = utils.get_members_and_supervisors(org)
                for m in mem:
                    if usernames_to_filter.count(m.username) == 0:
                       usernames_to_filter.append(m.username)
        else:
            is_member = True
            usernames_to_filter.append(content_obj.username)
 
    defs = FormDefData.objects.all()
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
    if is_supervisor:
        ret += '<td>%s</td>' % ("Group Aggregate")
    elif is_member:
        ret += '<td>%s</td>' % ("Current Report:")
    elif is_org:
        ret += '<td>%s</td>' % ("Org. Aggregate")
#    ret += '<td>%s</td>' % (content_obj)
    
    ret += '<td>%s</td>' % (time.strftime(output_format,last_submit.timetuple()))
    ret += '<td>%s</td>' % (count)   
    ret += '</tr>'    
    
    return ret


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
        
    

@register.simple_tag
def get_my_organization(extuser):    
    domain = extuser.domain    
    
    ctype = ContentType.objects.get_for_model(domain)
    root_orgs = Edge.objects.all().filter(parent_type=ctype,parent_id=domain.id,relationship__name='is domain root')
    if len(root_orgs) == 0:
        return '<h1>Error</h1>'
    root_org = root_orgs[0]
    
    descendents = traversal.getDescendentEdgesForObject(root_org.child_object)  #if we do domain, we go too high
    tbl = '<div class="reportheading"><table>'
    tbl += '<tr><td>Report</td><td>Last Submit</td><td>Count</td></tr></table></div>'
    
    
    
    if len(descendents) > 0:
        ret = '<div class="reports"><h4>Domain: ' + str(root_org.child_object) + '</h4><ul>' +tbl+ render_edgetree_as_ul(descendents,'children').__str__() + '</ul></div>'
        #ret += '<div class="reports"><h4>Reports</h4><ul>' + render_edgetree_reports_as_ul(descendents,'children') + '</ul></div>'
        return ret
    else:
        return '<div class="reports"><h4>No domain configuration found</h4></div>'    
    
    
