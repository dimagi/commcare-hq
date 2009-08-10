#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


from reports.models import Case
from shared import monitoring_report

'''Define custom reports in this file.  The rules are one module per
   domain and the module name must match _lowercase_ the domain name.  
   Each function in the module will then be listed as a custom report
   that should return html formatted text that will be displayed
   as the report. The doc string of the method is what will be 
   displayed in the UI (self documentation!).'''
   # This is still a bit of a work in progress.  

def monitoring(request):
    '''Safe Pregnancy Monitoring Report'''
    safe_preg_case_name = "MVP Safe Pregnancies"
    try:
        case = Case.objects.get(name=safe_preg_case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    
    return monitoring_report(request, case)
    