from organization.models import *
import logging
import string
from django.template.loader import render_to_string
from django.template import Template, Context
from datetime import datetime
from datetime import timedelta
import logging
import settings

import modelrelationship.traversal as traversal
import inspector as repinspector


def run_supervisor_reports(run_frequency):
    if run_frequency == 'daily':
        default_delta = timedelta(days=1)
        enddate = datetime.now()
        startdate = datetime.now() - default_delta    
    elif run_frequency == 'weekly':
        default_delta = timedelta(days=1)
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
    
    
    for report in ReportSchedule.objects.all().filter(report_class='supervisor').filter(report_frequency=run_frequency):
        print report.organization
        hierarchy = traversal.getDescendentEdgesForObject(report.organization)
        
        context = {}        
        context['content_item'] = report.organization                
        context['daterange_header'] = repinspector.get_daterange_header(startdate, enddate)
        context['results'] = repinspector.get_report_as_tuples(hierarchy, startdate, enddate, 0)
        
        rendered = render_to_string("organization/reports/email_hierarchy_report.html", context)        
        fout = open('report-org.html', 'w')
        fout.write(rendered)
        fout.close()
        
        for org in Organization.objects.all():
            context = {}        
            context['content_item'] = org                
            context['daterange_header'] = repinspector.get_daterange_header(startdate, enddate)
            hierarchy = traversal.getDescendentEdgesForObject(org)
            context['results'] = repinspector.get_report_as_tuples(hierarchy, startdate, enddate, 0)
            rendered = render_to_string("organization/reports/email_hierarchy_report.html", context)        
            fout = open('repor-org-' + org.name+ '.html', 'w')
            fout.write(rendered)
            fout.close()
            
            rendered = render_to_string("organization/reports/sms_organization.txt", context)        
            fout = open('repor-org-' + org.name+ '.txt', 'w')
            fout.write(rendered)
            fout.close()
        
        import organization.utils as utils
        
        
        (members, supervisors) = utils.get_members_and_supervisors(report.organization)
        
        
        
        for member in members:
            context = {}        
            context['content_item'] = member                
            context['daterange_header'] = repinspector.get_daterange_header(startdate, enddate)            
            context['results'] = [[0, None,member, repinspector.get_aggregate_count(member, startdate, enddate)]]
            rendered = render_to_string("organization/reports/email_hierarchy_report.html", context)        
            fout = open('reportmember-' + member.username + '.html', 'w')
            fout.write(rendered)
            fout.close()
            
            rendered = render_to_string("organization/reports/sms_organization.txt", context)        
            fout = open('reportmember-' + member.username + '.txt', 'w')
            fout.write(rendered)
            fout.close()
        for supervisor in supervisors:
            context = {}        
            context['content_item'] = supervisor                
            context['daterange_header'] = repinspector.get_daterange_header(startdate, enddate)            
            context['results'] = [[0, None,supervisor, repinspector.get_aggregate_count(supervisor, startdate, enddate)]]
            rendered = render_to_string("organization/reports/email_hierarchy_report.html", context)        
            fout = open('reportsupervisor-' + supervisor.username + '.html', 'w')
            fout.write(rendered)
            fout.close()
            
            rendered = render_to_string("organization/reports/sms_organization.txt", context)        
            fout = open('reportsupervisor-' + supervisor.username + '.txt', 'w')
            fout.write(rendered)
            fout.close()
            
                    
        
    return ''

def member_report(organization):
    return ''

def domain_report(domain):
    return ''
