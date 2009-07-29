from xformmanager.models import *
from organization.models import *
from reporters.models import Reporter, ReporterGroup
import organization.utils as utils        

import datetime
from datetime import timedelta


def get_stats_for_reporterprofile(reporter_profile, meta_qset, formdef_qset):
    """For a given reporterprofile object, we want to see what some certain stats are for their submissions.    
    requires a Metadata, and a FormDefModel queryset for filtration"""    
    
    statresults = {}    
    for_user = meta_qset.filter(username=reporter_profile.chw_username)
    
    statresults['Total Submissions'] = for_user.count()
    
    #Last recorded timestamp with patient
    statresults['Last timeend'] = for_user.order_by("-timeend")[0].timeend
    statresults['Last timeend Item'] = for_user.order_by("-timeend")[0].formname
    
    #last actual submission time recorded by server
    statresults['Last timeend Submission Time'] = for_user.order_by("-timeend")[0].submission.submission.submit_time
    statresults['Last Actual Submission Time'] = for_user.order_by("-submission__submission__submit_time")[0].submission.submission.submit_time
    
    #calculated metrics of interest
    days_since_submission = (datetime.datetime.now() - for_user.order_by("-submission__submission__submit_time")[0].submission.submission.submit_time).days
    statresults['Time since last submission (days)'] = days_since_submission
    if days_since_submission == 14: 
        #at the 2 week marker we want to send an alert.  
        #but we don't want continuous spam, so we just send it once just at the 2 week marker.        
        statresults['IdleWarning'] = True
    else:
        statresults['IdleWarning'] = False 
    return statresults

def get_stats_for_domain(domain):
    reporter_profiles = ReporterProfile.objects.filter(domain=domain)    
    #for a given domain, get all the formdefs
    fdefs_for_domain = FormDefModel.objects.filter(domain=domain)    
    #for all those formdefs, scan the metadata for parsed submissions
    allmetas_for_domain = Metadata.objects.filter(formdefmodel__in=fdefs_for_domain)   
    
    statdict = {}
    for rprof in reporter_profiles:
        statdict[rprof] = get_stats_for_reporterprofile(rprof,allmetas_for_domain,fdefs_for_domain)
    return statdict