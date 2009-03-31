from django import template
from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse

from modelrelationship.models import *
from django.contrib.contenttypes.models import ContentType
from types import ListType,TupleType

import modelrelationship.traversal as traversal
from modelrelationship.models import *

from organization.models import *

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
            if len(edges) > 1:    
                sublist += '\n<ul>'    
                sublist += render_edgetree_as_ul(edges,direction)
                sublist += '</ul>'
                sublist += '</ul>'
            else:               
                edge = edges[0]
                                        
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
                            
            subitems += '\t<li>'
            if direction == 'children':
                subitems += '<a href="%s?content_type=%s&content_id=%s">%s</a>' % (reverse('view_content_item', kwargs= {}),edge.child_type.id,edge.child_object.id,edge.child_object)         
            else:
                subitems += '<a href="%s?content_type=%s&content_id=%s">%s</a>' % (reverse('view_content_item', kwargs= {}),edge.parent_type.id,edge.parent_object.id,edge.parent_object)
            subitems += '\t</li>'                        
            subitems += '</li>'    
        
        if direction == 'children':
            fullret += subitems + sublist 
        else:
            fullret += subitems + sublist
    return fullret


@register.simple_tag
def get_my_organization(extuser):    
    domain = extuser.domain    
    
    ctype = ContentType.objects.get_for_model(domain)
    root_orgs = Edge.objects.all().filter(parent_type=ctype,parent_id=domain.id,relationship__name='is domain root')
    if len(root_orgs) == 0:
        return '<h1>Error</h1>'
    root_org = root_orgs[0]
    
    descendents = traversal.getDescendentEdgesForObject(root_org.child_object)
    if len(descendents) > 0:
        return '<div class="parents"><h4>' + str(root_org.child_object) + '</h4><ul>' + render_edgetree_as_ul(descendents,'children') + '</ul></div>'
    else:
        return '<div class="parents"><h4>No domain configuration found</h4></div>'    