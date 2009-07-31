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
from hq.reporter import metadata
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
    """Entry point for all reports in ReportSchedule to run 
    
    For a given frequency, ALL corresponding reports for that frequency will be queried and executed."""
    (startdate, enddate) = get_daterange(run_frequency)    
    logging.debug("running reports for " + run_frequency)
    
    
    for report in ReportSchedule.objects.all().filter(active=True, report_frequency=run_frequency):
        try:  
            logging.debug("running report " + str(report))
            #dmyung - note, this needs to be refactored ASAP to reflect the metadata based reports.
            if report.report_class == 'siteadmin':    
                #get the user id, then, get the report function.
                usr = report.recipient_user
                organization = report.organization
                if organization != None:
                    data = get_data_for_organization(run_frequency, report.report_delivery,organization)
                    logging.debug("got report data")                    
                    params = {}
                    heading = "Report for: " + startdate.strftime('%m/%d/%Y') + " - " + enddate.strftime('%m/%d/%Y')
                    params['heading'] = heading 
                    
                    if report.report_delivery == 'email':
                        subject = "[CommCare HQ] " + run_frequency + " report " + startdate.strftime('%m/%d/%Y') + "-" + enddate.strftime('%m/%d/%Y') + " ::  " + str(organization)
                        rendered_text = render_direct_email(data, startdate, enddate, "hq/reports/email_hierarchy_report.txt", params)
                        transport_email(rendered_text, usr, params={"startdate":startdate,"enddate":enddate,"email_subject":subject})
                    else:
                        rendered_text = render_direct_sms(data, startdate, enddate, "hq/reports/sms_organization.txt", params)
                        transport_sms(rendered_text, usr, params)
            elif report.report_class == 'supervisor' or report.report_class == 'member':
                #get the organization field and run the hierarchical report
                org = report.organization
                (members, supervisors) = utils.get_members_and_supervisors(org)                                
                orgdata = metadata.get_org_reportdata(org, startdate, enddate)
                params = {}
                if report.report_delivery == 'email':
                    params['heading'] = "User report for period: " + startdate.strftime('%m/%d/%Y') + " - " + enddate.strftime('%m/%d/%Y')
                    rendering_template = "hq/reports/email_hierarchy_report.txt"
                    renderfunc = render_direct_email
                    delivery_func = transport_email
                else:
                    params['heading'] = "Report " + startdate.strftime('%m/%d') + " - " + enddate.strftime('%m/%d/%Y')
                    rendering_template = "hq/reports/sms_organization.txt"
                    renderfunc = render_direct_sms 
                    delivery_func = transport_sms
                
                data = metadata.get_org_reportdata(org, startdate, enddate)                
                rendered_message =  renderfunc(data, startdate, enddate,     
                                                  rendering_template, 
                                                  params)               
                                   
                raise Exception("Delivery of metadata based supervisor/member reports not completed yet")
                if report.report_class == 'member':
                    for member in members:
                        delivery_func(member,rendered_text,params)                    
                else:
                    for super in supervisors:
                        delivery_func(rendered_text,[super.email], params)                
                logging.debug("report delivered")
            elif report.report_class == 'other':
                #Custom function.  We will check the attr for that function's existence and execute.      
                funcname = report.report_function
                logging.debug("Activating custom report function " + str(funcname))
                print "Activating custom report function " + str(funcname)
                if hasattr(custom, funcname):
                    func = getattr(custom,funcname)                              
                    func(report,run_frequency)                    
                    logging.debug("custom report complete")                    
                else:
                    logging.error("Error, report custom function " + str(funcname) + " does not exist")
        except Exception, e:
            logging.error("Error running " + run_frequency + " report: " + str(report) + " Exception: " + str(e))
                    
            
        
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
    print prepared_data
    print "prepared data"
    for item in prepared_data:
        sum = 0
        for num in item[-1]:sum+=num # single line, let's sum up the values            
        context['results'].append([item[2], sum])
    print "got the context"
    print context
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
        #until we get the rapidsms connection() stuff figured out, reveritng back to the extended user primary phone
        #ctell.send(recipient_usr.reporter.connection().identity, rendered_text)
        ctell.send(recipient_usr.primary_phone, rendered_text)
    except Exception, e:
        logging.error("Error sending SMS report to %s" % recipient_usr)
        logging.error(e)
    

