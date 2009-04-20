from django.core.mail import *

from django.template.loader import render_to_string
from django.template import Template, Context

import datetime
from datetime import timedelta
from organization.models import *
import logging



class EmailReporter(object):
    def __init___(self, host=None,username=None,password=None, use_tls=True,port=587):
        """The init uses gmail settings for outbound by default"""
        self.conn = SMTPConnection(port=port,
                                   host=host,
                                   password=password,
                                   use_tls=use_tls,
                                   fail_silently=False)
        
    def send_supervisor_dailyreport(self, supervisor_user):
        pass

    default_delta = timedelta(days=1)
    enddate = datetime.datetime.now()
    startdate = datetime.datetime.now() - default_delta    
        
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
