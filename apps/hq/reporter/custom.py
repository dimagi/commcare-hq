from hq.models import *
import logging
import string
from django.template.loader import render_to_string
from django.template import Template, Context
from datetime import datetime
from datetime import timedelta
import logging
import settings
import hq.utils as utils
from hq.reporter import agents        
import graphing.dbhelper as dbhelper
from xformmanager.models import *
from datetime import timedelta


import metastats as metastats
import inspector as repinspector

def _get_flat_data_for_domain(domain, startdate, enddate):
    
    data = []
    #next, let's get all the unclaimed
    #first, let's iterate through all the data and get the usernames
    #get all the usernames in question
    configured_users = []
    for datum in data:
        if isinstance(datum[2], ExtUser):
            configured_users.append(datum[2].report_identity.lower())        
    
    #next, do a query of all the forms in this domain to get an idea of all the usernames
    defs = FormDefModel.objects.all().filter(domain=domain)
    user_date_hash = {}
    
    for fdef in defs:
        try:
            helper = fdef.db_helper
            #let's get the usernames
            all_usernames = helper.get_uniques_for_column('meta_username')
            # hack!  manually set this for grameen
            if domain.name == "Grameen":
                all_usernames = ["mustafizurrahmna",
                                 "mdyusufali",
                                 "afrozaakter",
                                 "renuaraakter",
                                 "mostshahrinaakter",
                                 "shahanaakter",
                                 "sajedaparvin",
                                 "nasimabegum"
                                 ]
            #ok, so we got ALL usernames.  let's filter out the ones we've already seen
            unclaimed_users = []
            for existing in all_usernames:
                if existing:
                    if configured_users.count(existing.lower()) == 0:
                        unclaimed_users.append(existing.lower())
            
            #now that we've got ALL users, we can now the count query of their occurences in the formdef tables
            #as in the dashboard query, we need to hash it by username and by date to do the aggregate counts
            for user in all_usernames:                
                userdailies = helper.get_filtered_date_count(startdate, enddate,filters={'meta_username': user})
                if not user_date_hash.has_key(user):
                    user_date_hash[user] = {}
                for dat in userdailies:               
                    if not user_date_hash[user].has_key(dat[1]):
                        user_date_hash[user][dat[1]] = 0                   
                    user_date_hash[user][dat[1]] = user_date_hash[user][dat[1]] + int(dat[0]) #additive
        #end for loop through all the fdefs
        except Exception, e:
            # todo: this try/except is here for the weekly reports.  this is likely 
            # a real error that should not be getting swallowed
            logging.error(e)
        
    report_tuples = []
    #once all the formdefs have been calculated, we need to finally append the totals to the data array.  
    for usr, datehash in user_date_hash.items():
        
        #for a given user, make the 4 point array of their data
        usertuple = []
        usertuple.append(0)            
        if len(report_tuples) == 0:            
            usertuple.append('All Users')
        else:            
            usertuple.append(None)
            
        if unclaimed_users.count(usr) == 1:
            usertuple.append(usr + "*")
        else:
            usertuple.append(usr)
        udata = []
        
        totalspan = enddate - startdate
        for day in range(0,totalspan.days+1):
            delta = timedelta(days=day)
            target_date = startdate + delta
            datestr = target_date.strftime('%m/%d/%Y')
            if datehash.has_key(datestr):
                udata.append(datehash[datestr])
            else:
                udata.append(0)            
        usertuple.append(udata)            
        report_tuples.append(usertuple)                  
    #ok, so we just did all this data, let's append the data to the already existing data
    
    data = data + report_tuples  
    return data

def domain_flat(report_schedule, run_frequency):
    dom = report_schedule.hq.domain
    rendered_text = ''
    
    # DAN HACK: everyone wants the daily reports to show the last week's worth of data
    # so change this 
    if run_frequency == 'daily':
        run_frequency='weekly'    
    (startdate, enddate) = reporter.get_daterange(run_frequency)

    data = _get_flat_data_for_domain(dom, startdate, enddate)        
    params = {}
    heading = str(dom) + " report: " + startdate.strftime('%m/%d/%Y') + " - " + enddate.strftime('%m/%d/%Y')
    params['heading'] = heading    
    rendered_text += reporter.render_direct_email(data, startdate, enddate, "hq/reports/email_hierarchy_report.txt", params)

    if report_schedule.report_delivery == 'email':
        usr = report_schedule.recipient_user
        subject = "[CommCare HQ] " + run_frequency + " report " + startdate.strftime('%m/%d/%Y') + "-" + enddate.strftime('%m/%d/%Y') + " ::  Domain Report - " + str(dom)
        reporter.transport_email(rendered_text, usr, params={"startdate":startdate,"enddate":enddate,"email_subject":subject})


def admin_catch_all_flat(report_schedule, run_frequency):
    #same as admin_catch_all, but do for all users, no hqal junks
    domains = Domain.objects.all()
    rendered_text = ''
    from hq import reporter
    # DAN HACK: everyone wants the daily reports to show the last week's worth of data
    # so change this 
    if run_frequency == 'daily':
        run_frequency='weekly'    
    (startdate, enddate) = reporter.get_daterange(run_frequency)
    for dom in domains:
        #get the root organization
        data = _get_flat_data_for_domain(dom, startdate, enddate)        
        params = {}
        heading = str(dom) + " report: " + startdate.strftime('%m/%d/%Y') + " - " + enddate.strftime('%m/%d/%Y')
        params['heading'] = heading    
        rendered_text += reporter.render_direct_email(data, startdate, enddate, "hq/reports/email_hierarchy_report.txt", params)


    if report_schedule.report_delivery == 'email':
        usr = report_schedule.recipient_user
        subject = "[CommCare HQ] " + run_frequency + " report " + startdate.strftime('%m/%d/%Y') + "-" + enddate.strftime('%m/%d/%Y') + " ::  Global Admin"
        reporter.transport_email(rendered_text, usr, params={"startdate":startdate,"enddate":enddate,"email_subject":subject})


def admin_catch_all(report_schedule, run_frequency):
    #todo:  get all of the domains
    domains = Domain.objects.all()
    rendered_text = ''
    from hq import reporter
    # DAN HACK: everyone wants the daily reports to show the last week's worth of data
    # so change this 
    if run_frequency == 'daily':
        run_frequency='weekly'    
    (startdate, enddate) = reporter.get_daterange(run_frequency)
    for dom in domains:
        #get the root organization
        #TODO: clean this up
        # note: this pretty sneakily decides for you that you only care
        # about one root organization per domain.  should we lift this 
        # restriction?  otherwise this may hide data from you 
        root_orgs = Organization.objects.filter(parent=None, domain=extuser.domain)
        root_org = root_orgs[0]
    
        data = reporter.get_data_for_organization(run_frequency, report_schedule.report_delivery,root_org)
        params = {}
        heading = str(dom) + " report: " + startdate.strftime('%m/%d/%Y') + " - " + enddate.strftime('%m/%d/%Y')
        params['heading'] = heading 
        
        
        
        #next, let's get all the unclaimed
        #first, let's iterate through all the data and get the usernames
        #get all the usernames in question
        configured_users = []
        for datum in data:
            if isinstance(datum[2], ExtUser):
                configured_users.append(datum[2].report_identity.lower())
        
        
        #next, do a query of all the forms in this domain to get an idea of all the usernames
        defs = FormDefModel.objects.all().filter(domain=dom)
        user_date_hash = {}
        
        for fdef in defs:        
            helper = fdef.db_helper
            #let's get the usernames
            all_usernames = helper.get_uniques_for_column('meta_username')
            #ok, so we got ALL usernames.  let's filter out the ones we've already seen
            unclaimed_users = []
            for existing in all_usernames:
                if configured_users.count(existing.lower()) == 0:
                    unclaimed_users.append(existing.lower())
            
            #now that we've filtered out the unclaimed users, we can now the count query of their occurences in the formdef tables
            #as in the dashboard query, we need to hash it by username and by date to do the aggregate counts
            for user in unclaimed_users:                
                userdailies = helper.get_filtered_date_count(startdate, enddate,filters={'meta_username': user})
                if not user_date_hash.has_key(user):
                    user_date_hash[user] = {}
                for dat in userdailies:                
                    
                    if not user_date_hash[user].has_key(dat[1]):
                        user_date_hash[user][dat[1]] = 0                   
                    
                    user_date_hash[user][dat[1]] = user_date_hash[user][dat[1]] + int(dat[0]) #additive
        #end for loop through all the fdefs
        
        
        unclaimed_tuples = []
        #once all the formdefs have been calculated, we need to finally append the totals to the data array.  
        for unclaimed_user, datehash in user_date_hash.items():
            usertuple = []
            usertuple.append(1)
            if len(unclaimed_tuples) == 0:
                usertuple.append('Unassigned Users')
            else:
                usertuple.append(None)
            usertuple.append(unclaimed_user)
            udata = []
#            for dat, val in datehash.items():
#                udata.append(val)
            #let's walk through all the days in order to get the dates correct.
            
            totalspan = enddate - startdate
            for day in range(0,totalspan.days+1):
                delta = timedelta(days=day)
                target_date = startdate + delta
                datestr = target_date.strftime('%m/%d/%Y')
                if datehash.has_key(datestr):
                    udata.append(datehash[datestr])
                else:
                    udata.append(0)            
            usertuple.append(udata)            
            unclaimed_tuples.append(usertuple)                  
        #ok, so we just did all this data, let's append the data to the already existing data
        
        data = data + unclaimed_tuples        
        rendered_text += reporter.render_direct_email(data, startdate, enddate, "hq/reports/email_hierarchy_report.txt", params)

        
    if report_schedule.report_delivery == 'email':
        usr = report_schedule.recipient_user
        subject = "[CommCare HQ] " + run_frequency + " report " + startdate.strftime('%m/%d/%Y') + "-" + enddate.strftime('%m/%d/%Y') + " ::  Global Admin"
        reporter.transport_email(rendered_text, usr, params={"startdate":startdate,"enddate":enddate,"email_subject":subject})



def pf_swahili_sms(report_schedule, run_frequency):
    usr = report_schedule.recipient_user
    organization = report_schedule.organization
    org_domain = organization.domain
    transport = report_schedule.report_delivery
    if organization != None:
        from hq import reporter
        (startdate, enddate) = reporter.get_daterange(run_frequency)
        
        root_orgs = Organization.objects.filter(parent=None, domain=org_domain)
        # note: this pretty sneakily decides for you that you only care
        # about one root organization per domain.  should we lift this 
        # restriction?  otherwise this may hide data from you 
        root_org = root_orgs[0]
        # this call makes the meat of the report.
        report_payload = repinspector.get_data_below(root_org, startdate, enddate, 0)
        
        if transport == 'email':
            do_separate = True
        else:
            do_separate=False
            
        rendered_text = reporter.render_reportstring(org_domain, 
                   report_payload, 
                   run_frequency,
                   template_name="hq/reports/hack_sms_swahili.txt",                                       
                   transport=transport)
        reporter.deliver_report(usr, rendered_text, report_schedule.report_delivery,params={'startdate': startdate, 'enddate': enddate, 'frequency': run_frequency})                


def admin_per_form_report(report_schedule, run_frequency):
    # nothing calls this... which is good because it doesn't work
    org = report_schedule.organization
    transport = report_schedule.report_delivery   
    usr = report_schedule.recipient_user
    #report_txt = tree_report(organization, run_frequency, recipient=usr, transport=report.report_delivery)   
    
    from hq import reporter
    (startdate, enddate) = reporter.get_daterange(run_frequency)
    
    
    hierarchy = reporter.get_organizational_hierarchy(org.domain)
    
    defs = FormDefModel.objects.all().filter(domain=org.domain)
    
    fulltext = ''
    for fdef in defs:
        report_payload = repinspector.get_report_as_tuples_filtered(hierarchy, [fdef], startdate, enddate, 0)
        print "doing report for: " + str(fdef)
        if transport == 'email':
            do_separate = True
            params = {}
            heading = "Itemized report for " + fdef.form_display_name 
            params['heading'] = heading
            rendered_text = reporter.render_direct_email(report_payload, startdate, enddate, "hq/reports/email_hierarchy_report.txt", params)     
        else:
            do_separate=False
            
        fulltext += rendered_text
    newsubject = "[Commcare HQ] Itemized Report for: " + str(org)
    reporter.deliver_report(usr, fulltext, report_schedule.report_delivery,params={'startdate': startdate, 'enddate': enddate, 'frequency': run_frequency, 'email_subject': newsubject})

def delinquent_alert(report_schedule, run_frequency):    
    org = report_schedule.organization
    transport = report_schedule.report_delivery   
    usr = report_schedule.recipient_user    
    
    #dan hack.  circularly referring back to some methods in our namespace
    from hq import reporter    
    delinquents = []    
    statdict = metastats.get_stats_for_domain(org.domain)        
    for reporter_profile, result in statdict.items():
        if result.has_key('Time since last submission (days)'):
            lastseen = result['Time since last submission (days)']
        else:
            lastseen = 0
        if lastseen == 14:        
            delinquents.append(reporter_profile)    
    
    if len(delinquents) == 0:        
        logging.debug("No delinquent reporters, report will not be sent")        
        return        
    else:
        context = {}
        context['delinquent_reporterprofiles'] = delinquents
        rendered_text = render_to_string("hq/reports/sms_delinquent_report.txt",context)      
        
    if report_schedule.report_delivery == 'email':        
        subject = "[CommCare HQ] Daily Idle Reporter Alert for " + datetime.datetime.now().strftime('%m/%d/%Y')
        reporter.transport_email(rendered_text, usr, params={"email_subject":subject})
    else:
        reporter.transport_sms(rendered_text, usr)
