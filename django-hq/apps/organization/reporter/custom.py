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
from xformmanager.models import *

import inspector as repinspector


def admin_catch_all(report_schedule, run_frequency):
    #todo:  get all of the domains
    domains = Domain.objects.all()
    rendered_text = ''
    
    for dom in domains:
        #get the root organization
        from organization import reporter
        data = reporter.prepare_domain_or_organization(run_frequency, report.report_delivery,organization)
        params = {}
        heading = str(dom) + " report: " + startdate.strftime('%m/%d/%Y') + " - " + enddate.strftime('%m/%d/%Y')
        params['heading'] = heading 
        
        rendered_text += reporter.render_direct_email(data, run_frequency, "organization/reports/email_hierarchy_report.txt", params)
        
    if report.report_delivery == 'email':
        subject = "[CommCare HQ] " + run_frequency + " report " + startdate.strftime('%m/%d/%Y') + "-" + enddate.strftime('%m/%d/%Y') + " ::  Global Admin"
        reporter.transport_email(rendered_text, usr, params={"startdate":startdate,"enddate":enddate,"email_subject":subject})



def pf_swahili_sms(report_schedule, run_frequency):
    usr = report_schedule.recipient_user
    organization = report_schedule.organization
    org_domain = organization.domain
    transport = report_schedule.report_delivery
    if organization != None:
        from organization import reporter
        (startdate, enddate) = reporter.get_daterange(run_frequency)
        hierarchy = reporter.get_organizational_hierarchy(org_domain)
        report_payload = repinspector.get_report_as_tuples(hierarchy, startdate, enddate, 0)
        
        if transport == 'email':
            do_separate = True
        else:
            do_separate=False
            
        rendered_text = reporter.render_reportstring(org_domain, 
                   report_payload, 
                   run_frequency,
                   template_name="organization/reports/hack_sms_swahili.txt",                                       
                   transport=transport)
        reporter.deliver_report(usr, rendered_text, report_schedule.report_delivery,params={'startdate': startdate, 'enddate': enddate, 'frequency': run_frequency})                


def admin_per_form_report(report_schedule, run_frequency):    
    org = report_schedule.organization
    transport = report_schedule.report_delivery   
    usr = report_schedule.recipient_user
    #report_txt = tree_report(organization, run_frequency, recipient=usr, transport=report.report_delivery)   
    
    from organization import reporter
    (startdate, enddate) = reporter.get_daterange(run_frequency)
    
    
    hierarchy = reporter.get_organizational_hierarchy(org.domain)
    
    defs = FormDefData.objects.all().filter(uploaded_by__domain=org.domain)
    
    fulltext = ''
    for fdef in defs:
        report_payload = repinspector.get_report_as_tuples_filtered(hierarchy, [fdef], startdate, enddate, 0)
        print "doing report for: " + str(fdef)
        if transport == 'email':
            do_separate = True
            params = {}
            heading = "Itemized report for " + fdef.form_display_name 
            params['heading'] = heading
            rendered_text = reporter.render_direct_email(report_payload, run_frequency, "organization/reports/email_hierarchy_report.txt", params)     
        
        else:
            do_separate=False
        
        
        
        
        
#        rendered_text = reporter.render_reportstring(fdef.form_display_name, 
#                       report_payload, 
#                       run_frequency,                                       
#                       transport=transport)
        fulltext += rendered_text
    newsubject = "[Commcare HQ] Itemized Report for: " + str(org)
    reporter.deliver_report(usr, fulltext, report_schedule.report_delivery,params={'startdate': startdate, 'enddate': enddate, 'frequency': run_frequency, 'email_subject': newsubject})
    
    