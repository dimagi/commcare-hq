#
#import unittest
#import os
#from django.contrib.auth.models import Group, User
#from modelrelationship.models import *
#from organization.models import *
#from django.contrib.contenttypes.models import ContentType
#from django.core import serializers
#import logging
#
#import modelrelationship.traversal as traversal
#import organization.utils as utils
#
#class reportingTestCase(unittest.TestCase):
#    
#    def setUp(self):
#        from cchq_main.scripts import demo_bootstrap
#        demo_bootstrap.run()
#        logging.debug("bootstrapped")
#        
#        
#
#    def testDomainReport(self):
#        
#        domain = Domain.objects.all()[0]
#        descendents = traversal.getDescendentEdgesForObject(domain)  #if we do domain, we go too high
#        delta_week = timedelta(days=7)
#        delta_day= timedelta(days=1)
#        delta_month = timedelta(days=30)
#        delta_3month = timedelta(days=90)        
#        enddate = datetime.now()    
#        return get_report_as_tuples(descendents,enddate-delta_week, enddate,0)
#    
#    def testOrgReport(self):
#        org = Organization.objects.all()[0]
#        
#        descendents = traversal.getDescendentEdgesForObject(org)  #if we do domain, we go too high
#        delta_week = timedelta(days=7)
#        delta_day= timedelta(days=1)
#        delta_month = timedelta(days=30)
#        delta_3month = timedelta(days=90)        
#        enddate = datetime.now()    
#        return get_report_as_tuples(descendents,enddate-delta_week, enddate,0)
#    
#    def testSupervisor(self):
#        pass
#        
#    
#    def testMember(self):
#        pass
#    
#    def tearDown(self):
#        pass