#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from reports.models import Case
from shared import monitoring_report

'''Report file for custom Grameen reports'''
# see mvp.py for an explanation of how these are used.

# temporarily "privatizing" the name because grameen doesn't
# want this report to show up in the UI 
def _monitoring(request):
    '''Safe Pregnancy Monitoring Report'''
    safe_preg_case_name = "Grameen Safe Pregnancies"
    try:
        case = Case.objects.get(name=safe_preg_case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    
    return monitoring_report(request, case)
    
