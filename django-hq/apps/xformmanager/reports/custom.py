#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


from rapidsms.webui.utils import render_to_response
from django.http import HttpResponse
from django.template.loader import render_to_string

'''Define custom reports in this file.  The rules are one class per
   domain and the class name must match _exactly_ the domain name.  
   Each method in the class will then be listed as a custom report
   that should return html formatted text that will be displayed
   as the report. The doc string of the method is what will be 
   displayed in the UI (self documentation!).'''
   # This is still a bit of a work in progress.  I'm 
   # afraid how big this file will get if we don't find a 
   # way to split these out.

class MVP(object):
    '''Reports for the MVP domain'''

    def test(self, request):
        '''Proof of concept'''
        return "Cool a custom report!"
    
    def monitoring(self, request):
        '''Safe Pregnancy Monitoring Report'''
        context = { }
        # todo
        context["open_referrals"] = [1] * 5
        context["very_pregnant"] = [1] * 3
        context["approaching_visit"] = [1] * 7
        context["need_followup"] = [1] * 2
        return render_to_string("reports/mvp/monitoring.html", context)
    
    