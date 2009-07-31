from django.core.mail import *

from django.template.loader import render_to_string
from django.template import Template, Context

import datetime
from datetime import timedelta
from hq.models import *
import logging
import urllib2
import settings
import string

class ClickatellAgent(object):
    def __init__(self):
        logging.debug("clickatell initialized")
        self.clickatell_url = settings.CLICKATELL_URL 
        self.clickatell_user = settings.CLICKATELL_USER
        self.clickatell_password = settings.CLICKATELL_PASSWORD
        self.clickatell_api_id = settings.CLICKATELL_API_ID
        self.clickatell_mo = settings.CLICKATELL_MO 
        self.clickatell_number = settings.CLICKATELL_NUMBER
    
    #MessageForm = phone_number, body, outgoing (bool), 
    def send (self,phone_number, body, is_outgoing=True):        
        logging.info("got request for outgoing clickatell")
        logging.info("phone number: " + phone_number)        
        if phone_number == '':
            return
        
        #cleanup whitespaces
        lines = body.split('\n')
        trimbody = ''
        for line in lines:
            line = string.strip(line)
            if len(line) > 0:
                trimbody += line + "\n"
        body = trimbody       
        
        if len(body) > 135:
            parts = (len(body) / 135) + 1
            lines = body.split('\r')
            counter = 1
            currbody = ''
            for line in lines:
                line = string.strip(line)
                if len(currbody) + len(line) > 135:
                    totalcount = '%d/%d\n' % (counter,parts) 
                    self._do_send(phone_number, totalcount + currbody, is_outgoing)
                    currbody = line
                    counter = counter + 1
                else:
                    currbody = currbody + line
            if len(currbody.strip()) > 0:
                totalcount = '%d/%d\n' % (counter,parts) 
                self._do_send(phone_number, totalcount + currbody, is_outgoing)            
            pass
        else:
            self._do_send(phone_number,body,is_outgoing=True)
        
    
        
    def _do_send(self, phone_number, chunk, is_outgoing=True):        
        url = self.clickatell_url % (self.clickatell_user, self.clickatell_password, self.clickatell_api_id, phone_number, urllib2.quote(chunk), self.clickatell_mo, self.clickatell_number)
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


class EmailAgent(object):
    def __init__(self):
        """The init uses gmail settings for outbound by default"""
        self.conn = SMTPConnection(username=settings.EMAIL_LOGIN,
                                   port=settings.EMAIL_SMTP_PORT,
                                   host=settings.EMAIL_SMTP_HOST,
                                   password=settings.EMAIL_PASSWORD,
                                   use_tls=True,
                                   fail_silently=False)
        
    def send_email(self, subject, recipient_addr, msg_payload):
        #rendered = render_to_string("cvxpatient/synchronize.html", {'startdate': startdate, 'enddate':enddate})        
        msg = EmailMessage(subject=subject, #subj 
                           body=msg_payload, #body
                           from_email=settings.EMAIL_LOGIN, #from
                           to=[recipient_addr],#to
                           connection=self.conn
                           )
        
                           
        #attachname = 'report%s.html' % enddate.strftime('%Y-%m-%d')
        #msg.attach(attachname,rendered,"text/html")
        msg.content_subtype = "html"
        msg.send(fail_silently=False)
