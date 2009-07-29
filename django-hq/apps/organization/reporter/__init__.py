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

import inspector as repinspector

import custom

 
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
                data = get_data_for_organization(run_frequency, report.report_delivery,organization)
                params = {}
                heading = "Report for period: " + startdate.strftime('%m/%d/%Y') + " - " + enddate.strftime('%m/%d/%Y')
                params['heading'] = heading 
                
                if report.report_delivery == 'email':
                    subject = "[CommCare HQ] " + run_frequency + " report " + startdate.strftime('%m/%d/%Y') + "-" + enddate.strftime('%m/%d/%Y') + " ::  " + str(organization)
                    
                    rendered_text = render_direct_email(data, startdate, enddate, "organization/reports/email_hierarchy_report.txt", params)
                    transport_email(rendered_text, usr, params={"startdate":startdate,"enddate":enddate,"email_subject":subject})
                else:
                    rendered_text = render_direct_sms(data, startdate, enddate, "organization/reports/sms_organization.txt", params)
                    transport_sms(rendered_text, usr, params)
        elif report.report_class == 'supervisor' or report.report_class == 'member':
            #get the organization field and run the hierarchical report
            org = report.organization
            (members, supervisors) = utils.get_members_and_supervisors(org)
      
            data = get_data_for_organization(run_frequency, report.report_delivery, report.organization)                
            print "got data: " 
            print data
            if report.report_delivery == 'email':
                params = {}
                heading = "User report for period: " + startdate.strftime('%m/%d/%Y') + " - " + enddate.strftime('%m/%d/%Y')
                params['heading'] = heading
                rendered_text = render_direct_email(data, startdate, enddate, "organization/reports/email_hierarchy_report.txt", params)
                delivery_func = transport_email
                #transporter.email_report(usr,rendered_text, report.report_delivery, "")
                params={"subject":"blah",'startdate':startdate,'enddate':enddate, 'frequency':run_frequency}
            else:
                rendered_text = render_direct_sms(data, startdate, enddate, "")
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
            
        
def get_data_for_organization(run_frequency, transport, org_domain):
    (startdate, enddate) = get_daterange(run_frequency)
    return repinspector.get_data_below(org_domain, startdate, enddate, 0)
    
def render_direct_email(prepared_data, startdate, enddate, template_name, params={}):
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

def render_direct_sms(prepared_data, startdate, enddate, template_name, params={}):
    context = {}
    if params.has_key('heading'):
        context['report_heading'] = params['heading']
    else:
        raise Exception("Error to render an SMS, you must specify a heading")   
    
    #collpase the data
    context['results'] = []
    for item in prepared_data:
        sum = 0
        for num in item[-1]:sum+=num # single line, let's sum up the values            
        context['results'].append([item[2], sum])
    
    rendered = render_to_string(template_name, context)        
    return rendered




def transport_email(rendered_text, recipient_usr, params={}):
    logging.debug("Email Report transport")
    eml = agents.EmailAgent()            
    if params.has_key('email_subject'):
        subject_line = params['email_subject']        
    else:
        daterangestr = params['startdate'].strftime('%m/%d/%Y') + " - " + params['enddate'].strftime('%m/%d/%Y')
        subject_line = "[CommCare HQ] " + params['frequency'] + " report " + daterangestr
    eml.send_email(subject_line, recipient_usr.email, rendered_text)     
    
def transport_sms(rendered_text, recipient_usr, params={}):
    logging.debug("SMS Report transport via clickatell")        
    ctell = agents.ClickatellAgent()
    try:
        ctell.send(recipient_usr.reporter.connection().identity, rendered_text)
    except Exception, e:
        logging.error("Error sending SMS report to %s" % recipient_user)
        logging.error(e)
    

