from django.core.mail import *

from django.template.loader import render_to_string
from django.template import Template, Context

import datetime
from datetime import timedelta
from organization.models import *
import logging
import urllib2

class ClickatellReporter(object):
    def __init__(self):
        self.clickatell_url = "http://api.clickatell.com/http/sendmsg?user=%s&password=%s&api_id=%s&to=%s&text=%s&mo=%s&from=%s"
        self.clickatell_user = "dimagi"
        self.clickatell_password = "alpha123"
        self.clickatell_api_id = "3157202"
        self.clickatell_mo = "1"
        self.clickatell_number = "45609910343"
        self.clickatell = "clickatell"
    
    #MessageForm = phone_number, body, outgoing (bool), 
    def send (self,phone_number, body, is_outgoing=True):
        logging.info("got request for outgoing clickatell")
        url = self.clickatell_url % (self.clickatell_user, self.clickatell_password, self.clickatell_api_id, phone_number, urllib2.quote(body), self.clickatell_mo, self.clickatell_number)
        logging.info("url is " + url)
        for line in urllib2.urlopen(url):
            # czue - pretty hacky but this works - the response is soimething like 19:20804
            # where the first number is number of remaining credits, and the second is the
            # bernsoft id of the message
            split_string = line.split(":")
            if len(split_string) == 2:
                idstr, clickatell_id = split_string[0], split_string[1]
                logging.debug("Call back id: " + str(clickatell_id))     
            else:
                logging.debug("no response")           
                
        #back = "Url: " + url + "    Got back id: " +  call.external_id
        #back = "Got back id: " +  call.external_id
        #return render_to_response('shared/spitback.html', {'value' : back } )
        #return render_to_response('shared/spitback.html', {'value' : url } )


class EmailReporter(object):
    def __init___(self, host=None,username=None,password=None, use_tls=True,port=587):
        """The init uses gmail settings for outbound by default"""
        self.conn = SMTPConnection(port=port,
                                   host=host,
                                   password=password,
                                   use_tls=use_tls,
                                   fail_silently=False)
        
    def send_supervisor_dailyreport(self, supervisor_user):
        default_delta = timedelta(days=1)
        enddate = datetime.now()
        startdate = datetime.now() - default_delta    
            
        rendered = render_to_string("cvxpatient/synchronize.html", {'startdate': startdate, 'enddate':enddate})
        
        conn = SMTPConnection(port=587,
                              host='smtp.gmail.com',
                              username='dmyung@dimagi.com',
                              password='',
                              use_tls=True,
                              fail_silently=False)                  
        
        
        msg = EmailMessage('test from djanago', #subj 
                           "Test Daily Report", #body
                           'dmyung@dimagi.com', #from
                           ['dmyung@dimagi.com'],#to
                           connection=conn
                           )
        
                           
        attachname = 'report%s.html' % enddate.strftime('%Y-%m-%d')
        msg.attach(attachname,rendered,"text/html")
        msg.send(fail_silently=False)
