from organization.models import *
import logging
import string
from django.template.loader import render_to_string
from django.template import Template, Context
from datetime import datetime
from datetime import timedelta
import logging
import settings
import organization.utils as utils
from organization.reporter import agents
        

import modelrelationship.traversal as traversal
import inspector as repinspector

import custom

def get_organizational_hierarchy(org_or_user):
    filter_for = [EdgeType.objects.get(name='is parent organization'), EdgeType.objects.get(name='has supervisors'),EdgeType.objects.get(name='has members'), EdgeType.objects.get(name='is domain root')]
    hierarchy = traversal.getDescendentEdgesForObject(org_or_user, edgetype_include=filter_for)
    return hierarchy
 
def get_daterange(run_frequency):
    if run_frequency == 'daily':
        default_delta = timedelta(days=1)
        enddate = datetime.now()
        startdate = datetime.now() - default_delta    
    elif run_frequency == 'weekly':
        default_delta = timedelta(days=7)
        enddate = datetime.now()
        startdate = datetime.now() - default_delta    
    elif run_frequency == 'monthly':
        default_delta = timedelta(days=30)
        enddate = datetime.now()
        startdate = datetime.now() - default_delta    
    elif run_frequency == 'quarterly':
        default_delta = timedelta(days=90)
        enddate = datetime.now()
        startdate = datetime.now() - default_delta

    return (startdate, enddate)


    
def run_reports(run_frequency):
    (startdate, enddate) = get_daterange(run_frequency)

    for report in ReportSchedule.objects.all().filter(active=True):
        if report.report_class == 'siteadmin':
            #get the user id, then, get the report function.
            usr = report.recipient_user
            organization = report.organization
            if organization != None:
                report_txt = tree_report(organization, run_frequency, recipient=usr, transport=report.report_delivery)
                deliver_report(usr, report_txt, report.report_delivery,params={'startdate': startdate, 'enddate': enddate, 'frequency': run_frequency})                
            
        elif report.report_class == 'supervisor' or report.report_class == 'member':
            #get the organization field and run the hierarchical report
            org = report.organization
            report_txt = tree_report(org, run_frequency, transport=report.report_delivery)
            
            (members, supervisors) = utils.get_members_and_supervisors(org)
            
            if report.report_class == 'member':
                for member in members:
                    deliver_report(member, report_txt, report.report_delivery, params={'startdate': startdate, 'enddate': enddate, 'frequency': run_frequency})
            else:
                for super in supervisors:
                    deliver_report(super, report_txt, report.report_delivery, params={'startdate': startdate, 'enddate': enddate, 'frequency': run_frequency})
            
        elif report.report_class == 'other':
            #get the report function and proceed.
            print "others don't work yet"
        
 

def deprecated_run_all_reports(run_frequency):    
    """Run all reports that are relevant to the run frequency criteria"""
    (startdate, enddate) = get_daterange(run_frequency)
    for report in ReportSchedule.objects.all().filter(report_class='supervisor').filter(report_frequency=run_frequency):
        hierarchy = get_organizational_hierarchy(report.organization)
        
        context = {}        
        context['content_item'] = report.organization                
        context['daterange_header'] = repinspector.get_daterange_header(startdate, enddate)
        context['results'] = repinspector.get_report_as_tuples(hierarchy, startdate, enddate, 0)
        
        rendered = render_to_string("organization/reports/email_hierarchy_report.html", context)        
        fout = open('report-org.html', 'w')
        fout.write(rendered)
        fout.close()

#    for domain in Domain.objects.all():
#        tree_report(domain,run_frequency)
#    for org in Organization.objects.all():
#        tree_report(org, run_frequency)
#        supervisor_report(org, run_frequency)
#    for usr in ExtUser.objects.all():
#        user_report(usr, run_frequency)
        
    for domain in Domain.objects.all():
        tree_report(domain,run_frequency, transport='sms')
    for org in Organization.objects.all():
        tree_report(org, run_frequency, transport='sms')
        supervisor_report(org, run_frequency, transport='sms')
    for usr in ExtUser.objects.all():
        user_report(usr, run_frequency, transport='sms')

def deliver_report(usr_recipient, rendered_report, transport, params = {}):
    if transport == 'email':        
        eml = agents.EmailAgent()
        daterangestr = params['startdate'].strftime('%m/%d/%Y') + " - " + params['enddate'].strftime('%m/%d/%Y')        
        eml.send_email("[CommCare HQ] " + params['frequency'] + " report " + daterangestr, [usr_recipient.email], rendered_report)        
    elif transport == 'sms':
        logging.debug("transporting via clickatell")        
        ctell = agents.ClickatellAgent()
        ctell.send(usr_recipient.primary_phone, rendered_report)
    

def render_reportstring(content_item, report_payload, run_frequency, template_name="organization/reports/email_hierarchy_report.txt",  transport='email'):
    (startdate, enddate) = get_daterange(run_frequency)
    context = {}
    context['content_item'] = content_item
    context['daterange_header'] = repinspector.get_daterange_header(startdate, enddate)
    context['startdate'] = startdate
    context['enddate'] = enddate
    
    if transport == 'email':
        context['results'] = report_payload
        #leave the template name unchanged
    elif transport == 'sms':
        context['results'] = []
        for item in report_payload:
            sum = 0
            for num in item[-1]:sum+=num # single line, let's sum up the values
            
            context['results'].append([item[2], sum])
        template_name = "organization/reports/sms_organization.txt"
    
    rendered = render_to_string(template_name, context)        
    return rendered

#def user_report(user, run_frequency, transport='email'):    
#    (startdate, enddate) = get_daterange(run_frequency)
#    report_payload = []
#    report_payload.append([0, None ,user, repinspector.get_aggregate_count(user, startdate, enddate)])    
#    render_reportstring(user, report_payload, run_frequency, 'user-report-' + user.username + '.html', transport=transport)
#
#def supervisor_report(organization, run_frequency, transport='email'):
#    (startdate, enddate) = get_daterange(run_frequency)
#    (members, supervisors) = utils.get_members_and_supervisors(organization)        
#    context = {}    
#    report_payload = []
#    for member in members:                                            
#        report_payload.append([0, None,member, repinspector.get_aggregate_count(member, startdate, enddate)])
#    render_reportstring(organization, report_payload, run_frequency, 'supervisor-report-' + organization.name + '.html', transport=transport)  

def tree_report(org_domain, run_frequency, recipient=None, transport='email'):
    (startdate, enddate) = get_daterange(run_frequency)
    hierarchy = get_organizational_hierarchy(org_domain)
    report_payload = repinspector.get_report_as_tuples(hierarchy, startdate, enddate, 0)
    
    rendered_text = render_reportstring(org_domain, 
                   report_payload, 
                   run_frequency,                                       
                   transport=transport)
    
    return rendered_text  

    
