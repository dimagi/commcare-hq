from django.core.mail import *

from django.template.loader import render_to_string
from django.template import Template, Context

import datetime
from datetime import timedelta

default_delta = timedelta(days=1)
enddate = datetime.datetime.now()
startdate = datetime.datetime.now() - default_delta    

rendered = render_to_string('organization/dashboard.html', {'startdate': startdate, 'enddate':enddate})

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
