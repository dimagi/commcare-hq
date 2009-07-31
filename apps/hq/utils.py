
from hq.models import *
from graphing.models import *

from datetime import timedelta

PARENT_ORG_EDGE_TYPE=1
SUPERVISOR_EDGE_TYPE=2
MEMBER_EDGE_TYPE=3


#get members under this supervisor for this group
def get_members_for_supervisor(organization, supervisor_user):    
    pass

def get_supervisor_roles(extuser):
    """return an array of organizations that a user is a supervisor.  The array is empty if they are nothing"""
    raise Exception("Someone needs to fix this method to no longer be dependent on model relationship if they're going to use it!")
    
def get_membership(extuser):
    """return an array of organizations that a user belongs to.  The array is empty if they are nothing"""
    raise Exception("Someone needs to fix this method to no longer be dependent on model relationship if they're going to use it!")

def get_members(organization):
    """return an array of members in an organization"""
    raise Exception("Someone needs to fix this method to no longer be dependent on model relationship if they're going to use it!")

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
       to.
       The contents of the tuples are reporter objects.
       """
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
    raise Exception("Someone needs to fix this method to no longer be dependent on model relationship if they're going to use it!")
    
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
