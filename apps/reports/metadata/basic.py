""" 
Basic metadata reports/queries
@author: dan myung (dmyung@dimagi.com) 
create: 10/19/2009

Notes:
A place where oft reused queries off xformmanager.metadata can be referenced.

This is somewhat redundant with functionality already existent in the apps/reports/util.py file which already does
a basic metadata query.
"""

from domain.models import Domain
from hq.models import Organization, ReporterProfile, BlacklistedUser
from receiver.models import Submission
from reporters.models import Reporter, ReporterGroup
from datetime import datetime, timedelta
from xformmanager.models import Metadata


def build_filtered_metadataquery(intervalstart, intervalend, domain=None, reportergroup=None, reporterprofile=None, formdefs=[]):
    """
    Simple report function to prepare the metadata query for the eventual magic you will do to it.
    
    The required arguments are a timespan, and at least one of the following:
        Domain
        A single reporter group
        A single reporter profile
        or an array of formdatadef
        
    Returns the filtered Metadata queryset        
    """    
    if domain is None and reportergroup is None and reporterprofile is None and len(formdefs)== 0:
        raise Exception("Insufficient arguments to run query")
    
        
    filtered = Metadata.objects.filter(timeend__gte=intervalstart).filter(timeend__lte=intervalend)    
    exclude_usernames = []

    if domain != None:        
        #next, get the blacklisted users from this domain and exclude them
        blist = BlacklistedUser.objects.filter(domains=domain, active=True)
        exclude_usernames = blist.values_list('username',flat=True)
        
        filtered = filtered.filter(formdefmodel__domain=domain).exclude(username__in=exclude_usernames)
                  
        
    if reportergroup != None:
        raise Exception ("Reportergroup filtration not implemented yet")
    
    if reporterprofile != None:
        #note, consistency on chw_id vs. chw_username still needs to be worked out. for this usage, we'll stick to chw_username
        #chw_id should probably used long term 
        
        filtered = filtered.filter(username=reporterprofile.chw_username).exclude(username__in=exclude_usernames)
        
    if len(formdefs) > 0:
        filtered = filtered.filter(formdefmodel__in=formdefs).exclude(username__in=exclude_usernames)
    return filtered


def timeend_by_hour_of_day(intervalstart, intervalend, domain=None, reportergroup=None, reporterprofile=None, formdefs=[]):
    """
    Simple report function to get a histogram of the timeend by hour.
    The required arguments are a timespan, and at least one of the following:
        Domain
        A single reporter group
        A single reporter profile
        or an array of formdatadef
        
    This will return an array of counts, 24 in length for each hour with integers in it [1,4,1,2,4,2,...]    
    """
    
    filtered = build_filtered_metadataquery(intervalstart, intervalend, domain=domain, reportergroup=reportergroup, reporterprofile=reporterprofile, formdefs=formdefs)
    
    hourcounts = []
    for hour in range(0,24):    
        hourcounts.append(filtered.extra(where=['hour(timeend)=%d' % hour ]).count())
    return hourcounts

def timestart_by_hour_of_day(intervalstart, intervalend, domain=None, reportergroup=None, reporterprofile=None, formdefs=[]):
    """
    Simple report function to get a histogram of the timestart by hour.
    The required arguments are a timespan, and at least one of the following:
        Domain
        A single reporter group
        A single reporter profile
        or an array of formdatadef
        
    This will return an array of counts, 24 in length for each hour with integers in it [1,4,1,2,4,2,...]    
    """
    
    filtered = build_filtered_metadataquery(intervalstart, intervalend, domain=domain, reportergroup=reportergroup, reporterprofile=reporterprofile, formdefs=formdefs)
    
    hourcounts = []
    for hour in range(0,24):    
        hourcounts.append(filtered.extra(where=['hour(timestart)=%d' % hour ]).count())
    return hourcounts



def timedelta_by_hour_of_day(intervalstart, intervalend, domain=None, reportergroup=None, reporterprofile=None, formdefs=[]):
    """
    Simple report function to get a histogram of the average time delta of the timestart and timeeend, and show the results 
    by hour of the timeend.
    The required arguments are a timespan, and at least one of the following:
        Domain
        A single reporter group
        A single reporter profile
        or an array of formdatadef
        
    This will return an array of counts, 24 in length for each hour with integers in it [1,4,1,2,4,2,...]    
    """
    
    filtered = build_filtered_metadataquery(intervalstart, intervalend, domain=domain, reportergroup=reportergroup, reporterprofile=reporterprofile, formdefs=formdefs)
    
    hourcounts = []
    for hour in range(0,24):
        filterhour_timeend = filtered.extra(where=['hour(timeend)=%d' % hour ])
        totalseconds = 0
        for filt in filterhour_timeend:
            totalseconds = totalseconds + (filt.timeend - filt.timestart).seconds        
        if filterhour_timeend.count() > 0:
            avg = (totalseconds/filterhour_timeend.count())/60
        else:
            avg = -1
        hourcounts.append(avg)
    return hourcounts



def receivetime_by_hour_of_day(intervalstart, intervalend, domain=None, reportergroup=None, reporterprofile=None, formdefs=[]):
    """
    Simple report function to get a histogram of the time received by the server
    The required arguments are a timespan, and at least one of the following:
        Domain
        A single reporter group
        A single reporter profile
        or an array of formdatadef
        
    This will return an array of counts, 24 in length for each hour with integers in it [1,4,1,2,4,2,...]    
    """
    
    filtered = build_filtered_metadataquery(intervalstart, intervalend, domain=domain, reportergroup=reportergroup, reporterprofile=reporterprofile, formdefs=formdefs)
    #ok, so we got the filtered results, now we need to cross link it with the submissions to get the submit_time
    submission_ids = filtered.values_list('attachment__submission__id', flat=True)
    
    submissions = Submission.objects.filter(id__in=submission_ids)
    hourcounts = []
    for hour in range(0,24):    
        hourshift = (hour + 17)%24
        #hourshift = hour
        hourcounts.append(submissions.extra(where=['hour(submit_time)=%d' % hourshift ]).count())
    return hourcounts


def metadata_submission_stats(intervalstart, intervalend, domain=None, reportergroup=None, reporterprofile=None, formdefs=[]):
    """
    Using the same metadata filtration, establish stats on Metadata
    """
    
    filtered = build_filtered_metadataquery(intervalstart, intervalend, domain=domain, reportergroup=reportergroup, reporterprofile=reporterprofile, formdefs=formdefs)
    #total by deviceid
    #duplicates
    #metadata/users
    
    
    
    pass
    
    

