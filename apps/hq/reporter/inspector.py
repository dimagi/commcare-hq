from django import template
from django.contrib.contenttypes.models import ContentType
from types import ListType,TupleType

from xformmanager.models import *
from hq.models import *
import xformmanager.adapter.querytools as qtools
import hq.utils as utils
        

import time
from datetime import timedelta
import graphing.dbhelper as dbhelper

xmldate_format= '%Y-%m-%dT%H:%M:%S'
output_format = '%Y-%m-%d %H:%M'

username_datecount_cache = {}

def get_daterange_header(startdate, enddate, format_string='%m/%d/%Y', 
                         add_total=False):
    """Builds a daterange list for every day between two dates, 
       using a format string.  If specified will add a "total" 
       column to the end of the list""" 
    ret = []
    totalspan = enddate-startdate    
    for day in range(0,totalspan.days+1):   
        delta = timedelta(days=day)
        target_date = startdate + delta
        ret.append(target_date.strftime(format_string))

    if add_total:
        ret.append("Total")
    return ret

def get_user_forms_count(domain, username, startdate=None, enddate=None, forms_to_filter = None):
    ret  = ''
    totalspan = enddate-startdate    
    day_count_hash = {}
    #print 'get_user_allforms_count'
    for day in range(0,totalspan.days+1):
        delta = timedelta(days=day)
        target_date = startdate + delta
        #print "get_user_allforms_count: %s" % (str(target_date))
        day_count_hash[target_date.strftime('%m/%d/%Y')] = 0
    
    if forms_to_filter == None:    
        defs = FormDefModel.objects.all().filter(domain=domain)
    else:
        defs = forms_to_filter
    
    for fdef in defs:        
        helper = fdef.db_helper
        # TODO: blacklist isn't applied here.  Should it be?
        userdailies = helper.get_filtered_date_count(startdate, enddate,filters={'meta_username': username})                        
        for dat in userdailies:         
            #dt = time.strptime(str(dat[1][0:-4]),xmldate_format)
            #datum = datetime(dt[0],dt[1],dt[2],dt[3],dt[4],dt[5],dt[6])
            #day_count_hash[datum.strftime('%m/%d/%Y')] += int(dat[0])    
            day_count_hash[dat[1]] += int(dat[0])
    
    #print day_count_hash
    return day_count_hash


def get_aggregate_count(content_obj, startdate, enddate,forms_to_filter=None):
    """For a given content object, presumably it's a organization or a user, 
       it'll query all the xforms in its domain and see what the aggregate 
       counts of all submissions it has under itself"""
    
    if not content_obj:
        return 0 
    usernames_to_filter = []    

    totalspan = enddate-startdate    
    master_date_hash = {}
        
    for day in range(0,totalspan.days+1):
        delta = timedelta(days=day)
        target_date = startdate + delta
        master_date_hash[target_date.strftime('%m/%d/%Y')] = 0

    is_supervisor = False
    is_org = False
    is_member = False
    domain = None
    
    if isinstance(content_obj, Organization):
        is_org = True        
        domain  = content_obj.domain
        (members, supervisors) = utils.get_members_and_supervisors(content_obj)        
        for member in members:
            # only include these if we have a valid mapping to a chw_id
            try:
                usernames_to_filter.append(member.profile.get().report_identity)
            except ReporterProfile.DoesNotExist:
                # this is an okay error - just don't include them
                pass
        for supervisor in supervisors:
            try:
                usernames_to_filter.append(supervisor.profile.get().report_identity)
            except ReporterProfile.DoesNotExist:
                # this is an okay error - just don't include them
                pass
    elif isinstance(content_obj, User):        
        # CZUE: this could very likely blow up on us.  There is no
        # guarantee that this object exists
        domain  = content_obj.domain_membership.filter(is_active=True)[0]
        
        supervising_orgs = utils.get_supervisor_roles(content_obj)
        usernames_to_filter.append(content_obj.report_identity)
        is_member = True        
    
    for user in usernames_to_filter:
        if not username_datecount_cache.has_key(user):
            username_datecount_cache[user] = get_user_forms_count(domain, user, startdate, enddate,forms_to_filter=forms_to_filter)
            
        for target_date in username_datecount_cache[user].keys():
            master_date_hash[target_date] += username_datecount_cache[user][target_date]
    
    row = []
    
    for day in range(0,totalspan.days+1):        
        delta = timedelta(days=day)        
        target_date = startdate + delta
        val = master_date_hash[target_date.strftime('%m/%d/%Y')]        
        row.append(val)        
    
    return row



def get_single_org_data(organization, startdate, enddate):
    fullret = []
    fullret.append(get_single_item(None, organization, startdate, enddate, 0))
    members, supervisors = utils.get_members_and_supervisors(organization)
    is_first = True
    for supervisor in supervisors:
        # leaving the hack in that everything after the first is expected
        # to have a "None" description.  This should be revisited
        if is_first: 
            fullret.append(get_single_item("Supervisors", supervisor, startdate, enddate, 1))
            is_first = False
        else: 
            fullret.append(get_single_item(None, supervisor, startdate, enddate, 1))
    
    is_first = True #reset the first of the supervisors
    for member in members:
        if is_first:
            fullret.append(get_single_item("Members", member, startdate, enddate, 1))
            is_first = False
        else: 
            fullret.append(get_single_item(None, member, startdate, enddate, 1))
    
    return fullret

def get_data_below(organization, startdate, enddate, depth):
    """Do a lookukp of the organizations children and flattens
       the recursive return into 
       a simple array of items in the format:
       [recursiondepth, descriptor, item, report_rowdata] """
    
    fullret = []
        
    for child_org in organization.children.all():
        # add the child organization itself
        fullret.append(get_single_item(None, child_org, startdate, enddate, depth))
        members, supervisors = utils.get_members_and_supervisors(child_org)
        # add supervisor/member counts
        is_first = True
        for supervisor in supervisors:
            # leaving the hack in that everything after the first is expected
            # to have a "None" description.  This should be revisited
            if is_first: 
                fullret.append(get_single_item("Supervisors", supervisor, startdate, enddate, depth + 1))
                is_first = False
            else: 
                fullret.append(get_single_item(None, supervisor, startdate, enddate, depth + 1))
        is_first = True
        for member in members:
            if is_first:
                fullret.append(get_single_item("Members", member, startdate, enddate, depth + 1))
                is_first = False
            else: 
                fullret.append(get_single_item(None, member, startdate, enddate, depth + 1))
        
        # and don't forget to recurse through this child's children, if they 
        # exist
        fullret += get_data_below(child_org, startdate, enddate, depth + 1)
    
    # CZUE: 6/9/2009 this was in the previous implementation.  I don't exactly
    # know how the cache works, but I'm leaving it in.
    if depth == 0:
        username_datecount_cache.clear()    
    return fullret

def get_single_item(type, item, startdate, enddate, depth):
    """renders a report item into the appropriate structure for the email/sms templates"""
    return [depth, type, item, get_aggregate_count(item, startdate, enddate)]
    
    """renders a report item into the appropriate structure for the email/sms templates"""
    return [depth, type, item, get_aggregate_count(item, startdate, enddate)]
    
