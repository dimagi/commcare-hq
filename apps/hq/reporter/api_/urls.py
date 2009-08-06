from django.conf.urls.defaults import *
from django.http import HttpResponseBadRequest
from hq.reporter.api_.resources import *

urlpatterns = patterns('',
   #TODO - clean up index/value once we hash out this spec more properly
   (r'^api/reports/daily-report/', daily_report ),
   (r'^api/reports/user-report/', user_report ),
   (r'^api/reports/', read ),
   #(r'^api/reports/daily-report', 'ReportResource',
   #     {'ids': 9, \
   #      'index': 'day', 'value': 'count'} ),
   #(r'^api/reports/user-report', ReportResource().read, \
   #     {'ids': [ get_form_id_from_desc('referral') ], \
   #      'index': 'user', 'value': 'count'} ),
   # manually specify formdef_id until we figure out how to do authentication properly
   # TODO - filter returned data by user's domain
)

