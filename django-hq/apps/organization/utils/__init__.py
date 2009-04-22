
from modelrelationship.models import *
from organization.models import *
import modelrelationship.traversal as traversal

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
    (parents, children) = traversal.getImmediateRelationsForObject(extuser)
    
    for child_edge in children:
        if child_edge.relationship.name == "User Chart Group":
            return child_edge.child
    return None
    

def get_members_and_supervisors(organization):
    """Return a tuple (members[], supervisors[]) for a given organization"""
    (parents, children) = traversal.getImmediateRelationsForObject(organization)
    
    supervisors = []
    members = []
    for child_edge in children:
        if child_edge.relationship.id == MEMBER_EDGE_TYPE:   
            members.append(child_edge.child_object)
        elif child_edge.relationship.id == SUPERVISOR_EDGE_TYPE:
            supervisors.append(child_edge.child_object)            
    return (members, supervisors) 


def get_user_affiliation(extuser):
    (parents, children) = traversal.getImmediateRelationsForObject(extuser)
        
    membership = []
    for parent_edge in parents:
        if parent_edge.relationship.id == MEMBER_EDGE_TYPE or parent_edge.relationship.id == SUPERVISOR_EDGE_TYPE: 
            membership.append(parent_edge.parent_object)                    
    return membership