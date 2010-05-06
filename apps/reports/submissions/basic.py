""" 
Basic submission reports/queries
@author: dan myung (dmyung@dimagi.com) 
create: 10/23/2009

Notes:
A place where oft reused queries off receiver.submission can be referenced.
"""
from domain.models import Domain
from hq.models import Organization
from receiver.models import Submission, Attachment, SubmissionHandlingType, SubmissionHandlingOccurrence
from datetime import datetime, timedelta
import sets



def get_submission_stats(startdate, enddate, domain=None):
    """
    Return a tuple of statistics for a given date in the Receiver.
    (a,b,c,d)    
    """
    
    ret = {}    
    
    #get generic submissions    
    submits = Submission.objects.filter(submit_time__gte=startdate).filter(submit_time__lte=enddate)
    if domain != None:
        submits = submits.filter(domain=domain)
    ret['total_submissions'] = submits.count()    
    
    #values list returns non unique results. sets will reduce it, and doing a len will get us the cardinality
    unique_ips = len(set(submits.values_list('submit_ip', flat=True)))
    ret['total_unique_ips'] = unique_ips    

    soccurs = SubmissionHandlingOccurrence.objects.filter(submission__submit_time__gte=startdate).filter(submission__submit_time__lte=enddate)
    if domain != None:
        soccurs = soccurs.filter(submission__domain=domain)
    
    occur_types = SubmissionHandlingType.objects.all()
    for otype in occur_types:
        soccurs = soccurs.filter(handled=otype)
        ret[str(otype)] = soccurs.count() 
    
    #get duplicates    
    #unparsed attachments    
    #other bad stuff?    
    return ret
    