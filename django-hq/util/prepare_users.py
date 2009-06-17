
import os
import sys
import tarfile
import gzip
import string
import sys, os, select
import datetime

sys.path.append(os.path.join(os.path.dirname(__file__)))
sys.path.append(os.path.join(os.path.dirname(__file__),'..','apps'))
sys.path.append(os.path.join(os.path.dirname(__file__),'..','projects'))
sys.path.append(os.path.join(os.path.dirname(__file__),'..','projects','cchq_main'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'cchq_main.settings'


from organization.models import *
from modelrelationship.models import *




def create_extuser(userhash, domain, email=''):
    
    fullname = userhash['fullname']
    parts = fullname.split(' ')
    print parts
    firstname = parts[0]
    lastname = string.join(parts[1:],'')
    
    organization_extuser_1 = ExtUser()
    organization_extuser_1.username = firstname + "_" + lastname
    organization_extuser_1.first_name = firstname
    organization_extuser_1.last_name = lastname
    organization_extuser_1.email = email
    organization_extuser_1.password = 'blah'
    organization_extuser_1.is_staff = False
    organization_extuser_1.is_active = True
    organization_extuser_1.is_superuser = True
    organization_extuser_1.last_login = datetime(2009, 4, 15, 10, 33, 29)
    organization_extuser_1.date_joined = datetime(2009, 4, 15, 10, 33, 29)
    organization_extuser_1.primary_phone = userhash['primary_phone']
    organization_extuser_1.domain = domain
    organization_extuser_1.identity = None
    organization_extuser_1.chw_id = userhash['chw_id']
    organization_extuser_1.chw_username = userhash['chw_username']
    
    organization_extuser_1.save()
    return organization_extuser_1

def get_organization(org_name):
    orgs = Organization.objects.all().filter(name=org_name)
    if len(orgs) == 0:
        raise "That organization doesn't exist"
    else:
        return orgs[0]


def get_domain(domain_name):
    domains = Domain.objects.all().filter(name=domain_name)
    if len(domains) == 0:
        raise "That domain doesn't exist"
    else:
        return domains[0]
    
    
def create_edge(relationship_type, organization, extuser):
    if relationship_type == 'member':
        rel = EdgeType.objects.all().get(description='Organization Group Members')
    elif relationship_type == 'supervisor':
        rel = EdgeType.objects.all().get(description='Organization Supervisor')
        
    newedge = Edge()
    newedge.child_type = ContentType.objects.get(app_label="organization", model="extuser")
    newedge.child_id = extuser.id
    newedge.relationship = rel
    newedge.parent_type = ContentType.objects.get(app_label="organization", model="organization")
    newedge.parent_id = organization.id
    newedge.save()

    
    
    
    




if __name__ == "__main__":    
    if len(sys.argv) != 2:
            print """\tUsage: 
                prepare_environment.py
                     <userfile>                     
                    """                    
            sys.exit(1)
    else:
        userfile = sys.argv[-1]
        if os.path.exists(userfile):
            fin = open(userfile,'r')
            data = fin.read()
            fin.close()
            arr = eval(data)
            
            for hash in arr:
                
                domain = get_domain(hash['domain'])
                org = get_organization(hash['organization'])
                affiliation = hash['membership']
                
                usr = create_extuser(hash, domain)
                create_edge(affiliation, org, usr)
            