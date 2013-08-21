from datetime import datetime
import os

from django.http import HttpRequest
from django.test import TestCase
from bihar.reports.due_list import VaccinationSummary, get_due_list_by_task_name, get_due_list_records
from corehq.apps.users.models import WebUser

DIR_PATH = os.path.abspath(os.path.dirname(__file__))
test_data_location = os.path.join(DIR_PATH, 'opm_test.json')

class TestBeneficiary(TestCase):
    
    def setUp(self):
        print "case is being set up!"

    def test_something(self):
        print "testing something"
        self.assertEquals(1, 1)

    def test_other_thing(self):
        print "testing other_thing"
        self.assertEquals(1, 1)

        
# class TestDueList(TestCase):
#     """
#     Tests the Due List function superficially 
#     """
    
#     def test_due_list_by_task_name(self):
#         '''
#         Basic sanity check that the function does not crash and decomposes
#         the facet properly
#         '''
#         es = FakeES()
#         due_list = list(get_due_list_by_task_name(datetime.utcnow(), case_es=es))
#         self.assertEquals(due_list, [('foo', 10)])


#     def test_get_due_list_records(self):
#         '''
#         Basic sanity check that the function does not crash and decomposes
#         the records properly
#         '''
#         es = FakeES()
#         es.add_doc('foozle', {'foo': 'bar'})
#         es.add_doc('boozle', {'fizzle': 'bizzle'})
#         due_list_records = list(get_due_list_records(datetime.utcnow(), case_es=es))
#         self.assertEquals(due_list_records, [{'foo': 'bar'}, {'fizzle': 'bizzle'}])
