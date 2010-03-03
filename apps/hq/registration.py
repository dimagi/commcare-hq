from django import template
from django.contrib.contenttypes.models import ContentType
from types import ListType,TupleType

from xformmanager.models import *
from hq.models import *
from reporters.models import Reporter, ReporterGroup
import xformmanager.adapter.querytools as qtools
import hq.utils as utils        
import uuid
import string

import time
from datetime import timedelta

def autoregister_reporters(domain):
    """Scan the metadata to see all submissions and autoregister Reporter 
       and ReporterProfile for pending approval for the domain"""

    #for a given domain, get all the formdefs
    fdefs = FormDefModel.objects.filter(domain=domain)
    
    #for all those formdefs, scan the metadata for parsed submissions
    allmetas_for_domain = Metadata.objects.filter(formdefmodel__in=fdefs)
    
    username_tuples = allmetas_for_domain.values_list('username').distinct()
    
    #the values_list returns a list of tuples, so we need to flip it into a list
    # from [(),()...] to [...] 
    usernames = []
    for uname in username_tuples:
        usernames.append(uname[0])
        
    
    seen_profiles = ReporterProfile.objects.filter(domain=domain).filter(chw_username__in=usernames)    

    new_profiles = []
    for uname in usernames:
        if seen_profiles.filter(chw_username=uname).count() == 0:
            new_profiles.append(uname)
            
    
    for prof in new_profiles:
        #create a new ReporterProfile
        chw_id = allmetas_for_domain.filter(username=prof)[0].chw_id
        
        newProf = ReporterProfile(chw_id=chw_id, chw_username=prof, domain=domain, guid=str(uuid.uuid1()).replace('-',''))
                
        #create a new Reporter
        rep = Reporter()                
        alias, fn, ln = Reporter.parse_name("%s %s" % ("chw", prof))        
        rep.first_name = fn
        rep.last_name = ln
        rep.alias = alias
        rep.save()
        
        newProf.reporter = rep        
        newProf.save()
        
        
        
        
        
            
    
    
    
    