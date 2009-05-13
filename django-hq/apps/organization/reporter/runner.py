#from organization.models import *
#import logging
#import string
#from django.template.loader import render_to_string
#from django.template import Template, Context
#from datetime import datetime
#from datetime import timedelta
#import logging
#import settings
#import organization.utils as utils
#from organization.reporter import agents
#
#
#class BaseReporter(object):        
#    def __init__(self, run_frequency, startdate, enddate):
#        self.email_agent = agents.EmailAgent()
#        self.sms_agent = agents.ClickatellAgent()
#        
#        self.frequency = run_frequency
#        self.startdate = startdate
#        self.enddate = enddate
#        
#        pass    
#    
#    def prepare(self):
#        pass
#    
#    def render(self):
#        pass
#
#    def deliver(self):
#        pass
#    
#    
