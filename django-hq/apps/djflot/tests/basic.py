import unittest
import os
from django.contrib.auth.models import Group, User
from modelrelationship.models import *
from organization.models import *
from django.contrib.contenttypes.models import ContentType
from django.core import serializers


from djflot.models import *
import djflot.dbhelper as dbhelper

class BasicTestCase(unittest.TestCase):
    def setup(self):
        RawGraph.objects.all().delete()
        
#
#    def testMakeNewGraph(self):
#        rawgraph  = RawGraph()
#        rawgraph.shortname = "test cumulative"
#        rawgraph.title = "test cumulative"
#        rawgraph.table_name = "x_http__www_commcare_org_brac_chp_homevisit_v0_0_1"
#        rawgraph.data_source = "commcarehq"
#        rawgraph.db_query = """select
#                                    timeend,
#                                    number_of_children,
#                                    num_of_baby 
#                                
#                                from x_http__www_commcare_org_brac_chp_homevisit_v0_0_1;"""
#        rawgraph.x_axis_label = "Time"
#        rawgraph.x_type = "Date"
#        rawgraph.series_labels="number of children, num of baby"
#        rawgraph.display_type = "cumulative line"
#        rawgraph.series_options = ''
#        
#        rawgraph.save()        
#        #self.assertEqual(1,RawGraph.objects.all().count())
#        
#        
#    def testDoQuery(self):
#        self.testMakeNewGraph()
#        graphs = RawGraph.objects.all()        
#        for graph in graphs:
#            rows = graph.get_dataset()
#            print rows
        
    