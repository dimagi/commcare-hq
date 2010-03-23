from datetime import datetime, timedelta
from django.template import Template, Context
from django.template.loader import render_to_string
from domain.models import Domain
from hq.models import *
from receiver.models import Submission, Attachment
from reports.custom.all.domain_summary import DomainSummary
from xformmanager.models import *
import graphing.dbhelper as dbhelper
import hq.utils as utils
import inspector as repinspector
import logging
import metastats as metastats



def _get_flat_data_for_domain(domain, startdate, enddate, use_blacklist=True):
    
    #next, let's get all the unclaimed
    #first, let's iterate through all the data and get the usernames
    #get all the usernames in question
    configured_users = []
    
    #next, do a query of all the forms in this domain to get an idea of all the usernames
    defs = FormDefModel.objects.all().filter(domain=domain)
    user_date_hash = {}
    
    for fdef in defs:
        try:
            helper = fdef.db_helper
            #let's get the usernames
            username_col = fdef.get_username_column()
            if not username_col:
                logging.error("unable to run report for %s, no username column found" % fdef)
                continue
            all_usernames = helper.get_uniques_for_column(username_col)
            #ok, so we got ALL usernames.  let's filter out the ones we've already seen
            unclaimed_users = []
            for existing in all_usernames:
                if existing:
                    if configured_users.count(existing.lower()) == 0:
                        unclaimed_users.append(existing.lower())
            
            if use_blacklist:
                if fdef.domain:
                    blacklist = BlacklistedUser.for_domain(fdef.domain)
                else:
                    blacklist = []
            #now that we've got ALL users, we can now the count query of their occurences in the formdef tables
            #as in the dashboard query, we need to hash it by username and by date to do the aggregate counts
            for user in all_usernames:
                if use_blacklist and user in blacklist:
                    continue
                userdailies = helper.get_filtered_date_count(startdate, enddate,filters={username_col: user})
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
            logging.error("Report run failed for domain: " + str(domain) + " Exception: " + str(e))
        
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
        total_count = 0
        for day in range(0,totalspan.days+1):
            delta = timedelta(days=day)
            target_date = startdate + delta
            datestr = target_date.strftime('%m/%d/%Y')
            if datehash.has_key(datestr):
                udata.append(datehash[datestr])
                total_count += datehash[datestr]
            else:
                udata.append(0)
        udata.append(total_count)
        usertuple.append(udata)            
        report_tuples.append(usertuple)                  
    
    return report_tuples

def admin_stats_summary(report_schedule, run_frequency):
    """The domain summary, total counts of forms/chws and and 
       breakdowns by form type and CHW"""
    all_data = []
    
    global_stats = {}
    global_stats["name"] = "Global Total"
    global_stats["submissions"] = Submission.objects.count()
    global_stats["attachments"] = Attachment.objects.count()
    global_stats["form_count"] = FormDefModel.objects.count()
    global_stats["count"] = Metadata.objects.count()
    global_stats["chw_count"] = Metadata.objects.values_list('username', flat=True).distinct().count()
    global_stats["first_submission"] = Submission.objects.order_by("submit_time")[0].submit_time
    global_stats["last_submission"] = Submission.objects.order_by("-submit_time")[0].submit_time
    all_data.append(global_stats)
    for domain in Domain.objects.all():
        summary = DomainSummary(domain)
        all_data.append(summary)
    body = render_to_string("hq/reports/global_stats.html", {"global_stats": all_data })
    # annoying import cause of circular dependencies.
    
    from hq import reporter
    reporter.transport_email(body, report_schedule.recipient_user, 
                    params={"email_subject": "CommCareHQ Global Stats Report %s" %\
                            datetime.now().date() })

                    
 
def domain_flat(report_schedule, run_frequency):
    '''A report that shows, per user, how many forms were submitted over
       time, for a single domain (the domain of the associated user)'''
    domains = Domain.active_for_user(report_schedule.recipient_user)
    title = "Domain Report - %s" % (", ".join([domain.name for domain in domains]))
    return _catch_all_report(report_schedule, run_frequency, domains, title)
    
def admin_catch_all_flat(report_schedule, run_frequency):
    '''A report that shows, per user, how many forms were submitted over
       time, for all domains in the system'''
    domains = Domain.objects.all()
    return _catch_all_report(report_schedule, run_frequency, domains, "Global Admin")
    
def _catch_all_report(report_schedule, run_frequency, domains, title):
    rendered_text = ''
    from hq import reporter
    # DAN HACK: everyone wants the daily reports to show the last week's worth of data
    # so change this 
    if run_frequency == 'daily':
        run_frequency='weekly'    
    (startdate, enddate) = reporter.get_daterange(run_frequency)
    
    for domain in domains:
        rendered_text += _get_catch_all_email_text(domain, startdate, enddate)
        
    if report_schedule.report_delivery == 'email':
        usr = report_schedule.recipient_user
        subject = "[CommCare HQ] %s report %s - %s :: %s" %\
                    (run_frequency, startdate.strftime('%m/%d/%Y'),
                     enddate.strftime('%m/%d/%Y'), title)
        reporter.transport_email(rendered_text, usr, params={"startdate":startdate,"enddate":enddate,"email_subject":subject})

def _get_catch_all_email_text(domain, startdate, enddate):
    data = _get_flat_data_for_domain(domain, startdate, enddate)        
    context = {}
    heading = "%s report: %s - %s" % (domain, startdate.strftime('%m/%d/%Y'), enddate.strftime('%m/%d/%Y'))
    context['report_heading'] = heading    
    context['daterange_header'] = repinspector.get_daterange_header(startdate, enddate, add_total=True)
    context['startdate'] = startdate
    context['enddate'] = enddate
    context['results'] = data
    return render_to_string("hq/reports/email_hierarchy_report.txt", context)
    

def pf_swahili_sms(report_schedule, run_frequency):
    """ 
    Generates an sms report of the form:
    'Number of visits this week: DeRenzi(5), Jackson(3), Lesh(1)'
    """
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
    threshold = 14

    statdict = metastats.get_stats_for_domain(org.domain)
    context = get_delinquent_context_from_statdict(statdict, threshold)
    rendered_text = render_to_string("hq/reports/sms_delinquent_report.txt",context)

    if report_schedule.report_delivery == 'email':        
        subject = "[CommCare HQ] Daily Idle Reporter Alert for " + datetime.datetime.now().strftime('%m/%d/%Y') + " " + str(threshold) + " day threshold"
        reporter.transport_email(rendered_text, usr, params={"email_subject":subject})
    else:
        reporter.transport_sms(rendered_text, usr)

def get_delinquent_context_from_statdict(statdict, threshold):
    delinquents = []
    for reporter_profile, result in statdict.items():
        if result.has_key('Time since last submission (days)'):
            lastseen = result['Time since last submission (days)']
        else:
            lastseen = 0
        if lastseen >= threshold:        
            delinquents.append(reporter_profile)    
    
    context = {}
    context['threshold'] = threshold
    context['delinquent_reporterprofiles'] = []
    if len(delinquents) == 0:
        logging.debug("No delinquent reporters, report will not be sent")        
        return context
    else:
        context['delinquent_reporterprofiles'] = delinquents
        context['threshold'] = threshold
        return context
