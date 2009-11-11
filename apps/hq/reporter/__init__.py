from hq.models import *
import logging
import string
import inspect
from django.template.loader import render_to_string
from django.template import Template, Context
from django.utils import translation
from datetime import datetime
from datetime import timedelta
import logging
import settings
import hq.utils as utils
from hq.reporter import agents        
from hq.reporter import metadata
import inspector as repinspector

from reports.util import get_custom_report_module, get_report_method
import base64
import urllib2
import urllib
import httplib

from urlparse import urlparse

import custom

 
def get_daterange(run_frequency):
    '''Get a daterange based on a display string for a frequency.
       valid inputs are: daily, weekly, monthly, or quarterly.  
       If it gets a string it doesn't understand it will default
       to 7 days (weekly).  The end date is always assumed to be
       tomorrow, since consumers of this API generally aren't 
       inclusive (they want to see all data up to and including 
       today by calling WHERE date < enddate.'''
    enddate = datetime.now().date() + timedelta(days=1)
    delta = timedelta(days=7)
    if run_frequency == 'daily':
        delta = timedelta(days=1)
    elif run_frequency == 'weekly':
        delta = timedelta(days=7)
    elif run_frequency == 'monthly':
        delta = timedelta(days=30)
    elif run_frequency == 'quarterly':
        delta = timedelta(days=90)
    startdate = enddate - delta    
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
                _debug_and_print("Activating custom report function " + str(funcname))
                if hasattr(custom, funcname):
                    func = getattr(custom,funcname)                              
                    func(report,run_frequency)                    
                    logging.debug("custom report complete")                    
                else:
                    logging.error("Error, report custom function " + str(funcname) + " does not exist")
            elif report.report_class == 'domain':
                # added this enum for the custom domained reports defined in 
                # apps/reports/<domain>.py
                if not report.domain or not report.report_function:
                    raise Exception("Domain report %s must have domain and function set."
                                    % report)
                _debug_and_print("Activating custom domain report function %s for domain %s." 
                                 % (report.report_function, report.domain))
                
                report_method = get_report_method(report.domain, report.report_function)
                if not report_method:
                    raise Exception("No report named %s found for %s" % 
                                    (report.report_function, report.domain))
                
                # alrighty, we found the method we want to run.
                
                # HACK!  For now try manually setting the language to swahili
                # as a proof of concept.  Eventually this will come from the 
                # attached reporter profile. 
                
                # So in django all management commands default to english for
                # some reason, so we have to manually activate the language rather than
                # just assuming it'll work with the settings.
                translation.activate('sw')
                try: 
                    # TODO: not all reports may be okay with us passing in an empty
                    # request object.  For the time being we assume that they are
                    
                    # pretty moderate hackiness here - if the report takes in a domain
                    # pass it in.
                    if "domain" in inspect.getargspec(report_method)[0]:
                        report_body = report_method(None, domain=report.domain)
                    else:
                        report_body = report_method(None)

                finally:
                    # make sure we set the default back.
                    translation.activate(settings.LANGUAGE_CODE)
                #_debug_and_print(report_body)
                transport_email(report_body, report.recipient_user, 
                                params={"startdate": startdate,
                                        "enddate": enddate,
                                        "email_subject": report_method.__doc__})
                
        except Exception, e:
            logging.error("Error running " + run_frequency + " report: " + str(report) + " Exception: " + str(e))
                    
def _debug_and_print(message):
    """Convenience method to debug and print a message, so that we don't 
       have to copy paste two lines of code everywhere"""
    logging.debug(message)
    print message 
        
def get_data_for_organization(run_frequency, transport, org_domain):
    (startdate, enddate) = get_daterange(run_frequency)
    return repinspector.get_data_below(org_domain, startdate, enddate, 0)
    
def render_direct_email(prepared_data, startdate, enddate, template_name, params={}):
    
    # CZUE: I hate this code.  This is a really bad level of encapsulation.
    # Oh yeah, pass in a template and we'll set some magic variables involving
    # the dates and pass them in.  This is some of the most confusing and 
    # poor coupling I've seen. 
    
    # We should destroy this beast.  
    
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
    logging.debug("SMS Report transport via RapidSMS backend")    
    try:       
        #Send a message to the rapidsms backend via the Ajax app
        #Call the messaging ajax http endpoint
        ajax_endpoint = urlparse("http://localhost/ajax/messaging/send_message")        
        conn = httplib.HTTPConnection(ajax_endpoint.netloc)        
        
        #do a POST with the correct submission passing the reporter ID.
        #For more more information see the messaging and ajax apps.
        conn.request('POST', 
                     ajax_endpoint.path, 
                     urllib.urlencode({'uid': recipient_usr.reporter.id, 'text': rendered_text}),
                     {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})
        resp = conn.getresponse()
        results = resp.read()                
    except Exception, e:
        logging.error("Error sending SMS report to %s" % recipient_usr)
        logging.error(e)
    

