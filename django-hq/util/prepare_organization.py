
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




def create_or_get_organization(name, description, domain, orgtype):
    orgs = Organization.objects.all().filter(name=org_name)
    if len(orgs) == 0:    
        organization_organization_1 = Organization()
        organization_organization_1.name = name
        organization_organization_1.domain = domain
        organization_organization_1.description = description
        organization_organization_1.save()
    
        organization_organization_1.organization_type.add(organization_organizationtype_1)
    else:
        return orgs[0]

def create_or_get_domain(name, desc):
    domains = Domain.objects.all().filter(name=org_name)
    if len(domains) == 0:
        organization_domain_1 = Domain()
        organization_domain_1.name = name
        organization_domain_1.description = desc
        organization_domain_1.save()
        
        organization_organizationtype_1 = OrganizationType()
        organization_organizationtype_1.name = name + "_default"
        organization_organizationtype_1.domain = organization_domain_1
        organization_organizationtype_1.description = name + "_default"
        organization_organizationtype_1.save()
        
        return organization_domain_1, organization_organizationtype_1
    else:
        return domains[0], OrganizationType.objects.filter(domain=domains[0])[0]


def create_edge(domain, organization):
    
    rel = EdgeType.objects.all().get(description='Domain Root')
        
    newedge = Edge()
    newedge.child_type = ContentType.objects.get(app_label="organization", model="organization")
    newedge.child_id = organization.id
    newedge.relationship = rel
    newedge.parent_type = ContentType.objects.get(app_label="organization", model="domain")
    newedge.parent_id = domain.id
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
            