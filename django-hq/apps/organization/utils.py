
from modelrelationship.models import *
from organization.models import *
from dbanalyzer.models import *
import modelrelationship.traversal as traversal

from datetime import timedelta

PARENT_ORG_EDGE_TYPE=1
SUPERVISOR_EDGE_TYPE=2
MEMBER_EDGE_TYPE=3


#get members under this supervisor for this group
def get_members_for_supervisor(organization, supervisor_user):    
    pass

def get_supervisor_roles(extuser):
    """return an array of organizations that a user is a supervisor.  The array is empty if they are nothing"""
    (parents, children) = traversal.getImmediateRelationsForObject(extuser)
    membership = []
    for parent_edge in parents:
        if parent_edge.relationship.id == SUPERVISOR_EDGE_TYPE: 
            membership.append(parent_edge.parent_object)                    
    return membership

def get_membership(extuser):
    """return an array of organizations that a user belongs to.  The array is empty if they are nothing"""
    (parents, children) = traversal.getImmediateRelationsForObject(extuser)
    membership = []
    for parent_edge in parents:
        if parent_edge.relationship.id == MEMBER_EDGE_TYPE: 
            membership.append(parent_edge.parent_object)                    
    return membership

def get_members(organization):
    """return an array of members in an organization"""
    (parents, children) = traversal.getImmediateRelationsForObject(organization)
    
    supervisors = []
    members = []
    for child_edge in children:
        if child_edge.relationship.id == MEMBER_EDGE_TYPE:   
            members.append(child_edge.child_object)                    
    return members 

def get_chart_group(extuser):
    # todo this makes a mean assumption there's only one
    # group 
    try:
        prefs = GraphPref.objects.get(user=extuser)
        return  prefs.root_graphs.all()[0]
    except GraphPref.DoesNotExist:
        return None


def get_members_and_supervisors(organization):
    """Return a tuple (members[], supervisors[]) for a given organization.
       Deals with the empty lists and null objects for you so you don't have 
       to."""
    members = []
    supervisors = []
    if organization:
        if organization.members:
            members = organization.members.reporters.all()
        if organization.supervisors:
            supervisors = organization.supervisors.reporters.all()  
    return (members, supervisors)
            
    
def get_user_affiliation(extuser):
    (parents, children) = traversal.getImmediateRelationsForObject(extuser)
        
    membership = []
    for parent_edge in parents:
        if parent_edge.relationship.id == MEMBER_EDGE_TYPE or parent_edge.relationship.id == SUPERVISOR_EDGE_TYPE: 
            membership.append(parent_edge.parent_object)                    
    return membership

def get_dates(request, default_days=0):
    default_delta = timedelta(days=default_days)
    enddate = datetime.datetime.now().date()
    startdate = enddate - default_delta
    
    for item in request.GET.items():
        if item[0] == 'startdate':
            startdate_str=item[1]
            startdate = datetime.datetime.strptime(startdate_str,'%m/%d/%Y')            
        if item[0] == 'enddate':
            enddate_str=item[1]
            enddate = datetime.datetime.strptime(enddate_str,'%m/%d/%Y')
    return (startdate, enddate)
