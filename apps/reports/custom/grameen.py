#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from django.template.loader import render_to_string
from django.db import connection
import settings

from xformmanager.models import Metadata, FormDefModel, ElementDefModel
from reports.models import Case, SqlReport
from reports.util import get_whereclause
from shared import monitoring_report, Mother


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

def _mother_summary(request):
    '''Individual Mother Summary'''
    # this is intentionally private, as it's only accessed from within other
    # reports that explicitly know about it.  We don't want to list it because
    # we don't know what id to use.
    safe_preg_case_name = "Grameen Safe Pregnancies"
    try:
        case = Case.objects.get(name=safe_preg_case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    if not "case_id" in request.GET:
        return '''Sorry, you have to specify a mother using the case id
                  in the URL.'''
    case_id = request.GET["case_id"]
    data = case.get_data_map_for_case(case_id)
    mom = Mother(case, case_id, data)
    
    return render_to_string("custom/grameen/mother_details.html", 
                            {"mother": mom})
    


def hi_risk_pregnancies(request):
    '''Hi-Risk Pregnancy Summary'''
    # just pass on to the helper view, but ensure that hi-risk is set to yes
    params = request.GET.copy()
    params["sampledata_hi_risk"]="yes"
    return _chw_submission_summary(request, params)
    
def chw_submission_details(request):
    '''Health Worker Submission Details'''
    return _chw_submission_summary(request, request.GET)

def _chw_submission_summary(request, params):
    # this was made a private method so that we can call it from multiple reports
    # with an extra parameter.
    
    # had to move this form a sql report to get in the custom annotations
    # this is a pretty ugly/hacky hybrid approach, and should certainly
    # be cleaned up
    extuser = request.extuser
    # hard coded to our fixture.  bad bad!
    grameen_submission_details_id = 2
    # hard coded to our schema.  bad bad!
    form_def = ElementDefModel.objects.get(table_name="schema_intel_grameen_safe_motherhood_registration_v0_3").form
    report = SqlReport.objects.get(id=grameen_submission_details_id)
    cols = ('meta_username', 'sampledata_hi_risk')
    where_cols = dict([(key, val) for key, val in params.items() if key in cols])
    whereclause = get_whereclause(where_cols)
    follow_filter = None
    if "follow" in params:
        if params["follow"] == "yes":
            follow_filter = True
        elif params["follow"] == "no":
            follow_filter = False
    cols, data = report.get_data({"whereclause": whereclause})
    new_data = []
    for row in data:
        new_row_data = dict(zip(cols, row))
        row_id = new_row_data["Instance ID"]
        meta = Metadata.objects.get(formdefmodel=form_def, raw_data=row_id)
        follow = meta.attachment.annotations.count() > 0
        if follow_filter is not None:
            if follow_filter and not follow:
                # filtering on true, but none found, don't include this
                continue
            elif not follow_filter and follow:
                # filtering on false, but found follows, don't include this
                continue
        
        new_row_data["Follow up?"] = "yes" if follow else "no"
        new_row_data["meta"] = meta
        new_row_data["attachment"] = meta.attachment
        new_data.append(new_row_data)
    cols = cols[:6]
    return render_to_string("custom/grameen/chw_submission_details.html", 
                            {"MEDIA_URL": settings.MEDIA_URL, # we pretty sneakly have to explicitly pass this
                             "columns": cols,
                             "data": new_data})
    

