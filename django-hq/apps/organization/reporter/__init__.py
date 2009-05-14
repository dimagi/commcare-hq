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
    print "running reports"
    for report in ReportSchedule.objects.all().filter(active=True, report_frequency=run_frequency):  
        if report.report_class == 'siteadmin':
            #get the user id, then, get the report function.
            usr = report.recipient_user
            organization = report.organization
            if organization != None:
                data = prepare_domain_or_organization(run_frequency, report.report_delivery,organization)
#                print "got data: " 
#                print data               
                params = {}
                heading = "Report for period: " + startdate.strftime('%m/%d/%Y') + " - " + enddate.strftime('%m/%d/%Y')
                params['heading'] = heading 
                
                if report.report_delivery == 'email':
                    subject = "[CommCare HQ] " + run_frequency + " report " + startdate.strftime('%m/%d/%Y') + "-" + enddate.strftime('%m/%d/%Y') + " ::  " + str(organization)
                    
                    rendered_text = render_direct_email(data, run_frequency, "organization/reports/email_hierarchy_report.txt", params)
                    transport_email(rendered_text, [usr.email],report.report_delivery, params={"startdate":startdate,"enddate":enddate,"email_subject":subject})
                else:
                    rendered_text = render_direct_sms(data, run_frequency, "organization/reports/sms_organization.txt")
                    transport_sms(usr,rendered_text, report.report_delivery)
                
                
                #report_txt = tree_report(organization, run_frequency, recipient=usr, transport=report.report_delivery)
                #deliver_report(usr, report_txt, report.report_delivery,params={'startdate': startdate, 'enddate': enddate, 'frequency': run_frequency})                
            
        elif report.report_class == 'supervisor' or report.report_class == 'member':
            #get the organization field and run the hierarchical report
            org = report.organization
#            report_txt = tree_report(org, run_frequency, transport=report.report_delivery)
#            
            (members, supervisors) = utils.get_members_and_supervisors(org)
#            
#            if report.report_class == 'member':
#                for member in members:
#                    deliver_report(member, report_txt, report.report_delivery, params={'startdate': startdate, 'enddate': enddate, 'frequency': run_frequency})
#            else:
#                for super in supervisors:
#                    deliver_report(super, report_txt, report.report_delivery, params={'startdate': startdate, 'enddate': enddate, 'frequency': run_frequency})
      
            data = prepare_domain_or_organization(run_frequency, report.report_delivery, report.organization)                
            print "got data: " 
            print data
            if report.report_delivery == 'email':
                params = {}
                heading = "User report for period: " + startdate.strftime('%m/%d/%Y') + " - " + enddate.strftime('%m/%d/%Y')
                params['heading'] = heading
                rendered_text = render_direct_email(data, run_frequency, "organization/reports/email_hierarchy_report.txt", params)
                delivery_func = transport_email
                #transporter.email_report(usr,rendered_text, report.report_delivery, "")
                params={"subject":"blah",'startdate':startdate,'enddate':enddate, 'frequency':run_frequency}
            else:
                rendered_text = render_direct_sms(data, run_frequency, "")
                delivery_func = transport_sms
                params = {}     
                
            if report.report_class == 'member':
                for member in members:
                    delivery_func(member,rendered_text,params)                    
            else:
                for super in supervisors:
                    delivery_func(rendered_text,[super.email], params)
                
                
        elif report.report_class == 'other':
            #get the report function and proceed.
            funcname = report.report_function
            print funcname
            if hasattr(custom, funcname):
                func = getattr(custom,funcname) 
                func(report,run_frequency)
            
        
 

#def deprecated_run_all_reports(run_frequency):    
#    """Run all reports that are relevant to the run frequency criteria"""
#    (startdate, enddate) = get_daterange(run_frequency)
#    for report in ReportSchedule.objects.all().filter(report_class='supervisor').filter(report_frequency=run_frequency):
#        hierarchy = get_organizational_hierarchy(report.organization)
#        
#        context = {}        
#        context['content_item'] = report.organization                
#        context['daterange_header'] = repinspector.get_daterange_header(startdate, enddate)
#        context['results'] = repinspector.get_report_as_tuples(hierarchy, startdate, enddate, 0)
#        
#        rendered = render_to_string("organization/reports/email_hierarchy_report.html", context)        
#        fout = open('report-org.html', 'w')
#        fout.write(rendered)
#        fout.close()
#
##    for domain in Domain.objects.all():
##        tree_report(domain,run_frequency)
##    for org in Organization.objects.all():
##        tree_report(org, run_frequency)
##        supervisor_report(org, run_frequency)
##    for usr in ExtUser.objects.all():
##        user_report(usr, run_frequency)
#        
#    for domain in Domain.objects.all():
#        tree_report(domain,run_frequency, transport='sms')
#    for org in Organization.objects.all():
#        tree_report(org, run_frequency, transport='sms')
#        supervisor_report(org, run_frequency, transport='sms')
#    for usr in ExtUser.objects.all():
#        user_report(usr, run_frequency, transport='sms')


def deliver_report(usr_recipient, rendered_report, transport, params = {}):
    if transport == 'email':        
        eml = agents.EmailAgent()
        daterangestr = params['startdate'].strftime('%m/%d/%Y') + " - " + params['enddate'].strftime('%m/%d/%Y')        
        if params.has_key('email_subject'):
            subject_line = params['email_subject']        
        else:
            subject_line = "[CommCare HQ] " + params['frequency'] + " report " + daterangestr
        eml.send_email(subject_line, [usr_recipient.email], rendered_report)        
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
#        template_name = "organization/reports/sms_organization.txt"
    
    rendered = render_to_string(template_name, context)        
    return rendered
#
#
#def tree_report(org_domain, run_frequency, recipient=None, transport='email'):
#    (startdate, enddate) = get_daterange(run_frequency)
#    hierarchy = get_organizational_hierarchy(org_domain)
#    report_payload = repinspector.get_report_as_tuples(hierarchy, startdate, enddate, 0)
#    
#    if transport == 'email':
#        do_separate = True
#    else:
#        do_separate=False
#    
#    
#    template_name = "organization/reports/sms_organization.txt"
#    rendered_text = render_reportstring(org_domain, 
#                   report_payload, 
#                   run_frequency,                                       
#                   transport=transport)
#    
#    return rendered_text  


def prepare_domain_or_organization(run_frequency, transport, org_domain):
    (startdate, enddate) = get_daterange(run_frequency)
    hierarchy = get_organizational_hierarchy(org_domain)
    prepared_data = repinspector.get_report_as_tuples(hierarchy, startdate, enddate, 0)    
    return prepared_data


def prepare_filtered_domain_or_organization(run_frequency, transport, org_domain, filtered_form):
    (startdate, enddate) = get_daterange(run_frequency)
    hierarchy = get_organizational_hierarchy(org_domain)
    prepared_data = repinspector.get_report_as_tuples(hierarchy, startdate, enddate, 0)    
    return prepared_data



def render_direct_email(prepared_data, run_frequency, template_name, params={}):
    (startdate, enddate) = get_daterange(run_frequency)
    context = {}
        
    context['daterange_header'] = repinspector.get_daterange_header(startdate, enddate)
    context['startdate'] = startdate
    context['enddate'] = enddate
    
    if params.has_key('heading'):
        context['report_heading'] = params['heading']
    else:
        raise Exception("Error to render an Email, you must specify a heading")
    
    context['results'] = prepared_data
    rendered = render_to_string(template_name, context)
    return rendered

def render_direct_sms(prepared_data, run_frequency, template_name, params={}):
    (startdate, enddate) = get_daterange(run_frequency)
    context = {}
    if params.has_key('heading'):
        context['report_heading'] = params['heading']
    else:
        raise Exception("Error to render an SMS, you must specify a heading")   
    
    #collpase the data
    context['results'] = []
    for item in report_payload:
        sum = 0
        for num in item[-1]:sum+=num # single line, let's sum up the values            
        context['results'].append([item[2], sum])        
    return rendered




def transport_email(rendered_text, recipients, params={}):
    logging.debug("Email Report transport")
    eml = agents.EmailAgent()
    daterangestr = params['startdate'].strftime('%m/%d/%Y') + " - " + params['enddate'].strftime('%m/%d/%Y')        
    if params.has_key('email_subject'):
        subject_line = params['email_subject']        
    else:
        subject_line = "[CommCare HQ] " + params['frequency'] + " report " + daterangestr
    eml.send_email(subject_line, recipients, rendered_text)     
    
def transport_sms(rendered_text, recipients, params={}):
    logging.debug("SMS Report transport via clickatell")        
    ctell = agents.ClickatellAgent()
    ctell.send(usr_recipient.primary_phone, rendered_text)

