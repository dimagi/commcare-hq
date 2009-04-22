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

import modelrelationship.traversal as traversal
import inspector as repinspector

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

def run_all_reports(run_frequency):    
    (startdate, enddate) = get_daterange(run_frequency)
    for report in ReportSchedule.objects.all().filter(report_class='supervisor').filter(report_frequency=run_frequency):
        hierarchy = traversal.getDescendentEdgesForObject(report.organization)
        
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
    

def process_report(content_item, report_payload, run_frequency, filename,template_name="organization/reports/email_hierarchy_report.html",  transport='email'):
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
            for num in item[-1]:sum+=num
            context['results'].append([item[2], sum])
        template_name = "organization/reports/sms_organization.txt"
    
    rendered = render_to_string(template_name, context)        
    fout = open(filename, 'w')
    fout.write(rendered)
    fout.close()    


def user_report(user, run_frequency, transport='email'):    
    (startdate, enddate) = get_daterange(run_frequency)
    report_payload = []
    report_payload.append([0, None ,user, repinspector.get_aggregate_count(user, startdate, enddate)])   
    
    process_report(user, report_payload, run_frequency, 'user-report-' + user.username + '.html', transport=transport)
        

def supervisor_report(organization, run_frequency, transport='email'):
    (startdate, enddate) = get_daterange(run_frequency)
    (members, supervisors) = utils.get_members_and_supervisors(organization)        
    context = {}    
    report_payload = []
    for member in members:                                            
        report_payload.append([0, None,member, repinspector.get_aggregate_count(member, startdate, enddate)])    

    process_report(organization, report_payload, run_frequency, 'supervisor-report-' + organization.name + '.html', transport=transport)  
    

def tree_report(org_domain, run_frequency, transport='email'):
    (startdate, enddate) = get_daterange(run_frequency)
    hierarchy = traversal.getDescendentEdgesForObject(org_domain)
    report_payload = repinspector.get_report_as_tuples(hierarchy, startdate, enddate, 0)
    
    process_report(org_domain, report_payload, run_frequency, 'report-org-' + org_domain.name + '.html', transport=transport)  

    
