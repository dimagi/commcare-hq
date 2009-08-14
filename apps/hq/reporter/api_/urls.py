from django.conf.urls.defaults import *
from django.http import HttpResponseBadRequest
from hq.reporter.api_.resources import *

def _get_form_id_from_desc(desc):
    formdefs = FormDefModel.objects.filter(target_namespace__icontains=desc)
    return [ f.pk for f in formdefs ]

urlpatterns = patterns('',
   (r'^api/reports/daily-report', report, \
       {'ids': _get_form_id_from_desc('resolution_0.0.2'), \
        'index': 'Day', 'value': ['Referrals']} ),
   (r'^api/reports/user-report', report, \
        {'ids': _get_form_id_from_desc('resolution_0.0.2'), \
         'index': 'User', 'value': ['Referrals']} ),
   (r'^api/reports/', report ),
)
