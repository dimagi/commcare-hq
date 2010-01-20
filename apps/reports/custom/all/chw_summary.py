from datetime import datetime, timedelta

from django.template.loader import render_to_string

from xformmanager.models import Metadata
from graphing.dbhelper import DbHelper
from hq.utils import get_dates_reports

from hq.models import Domain, Organization, ReporterProfile
from reports.custom.util import forms_submitted
from apps.reports.models import Case, CaseFormIdentifier

def chw_summary(request, domain=None):
    '''The chw_summary report'''
    if not domain:
        domain = request.extuser.domain
    # to configure these numbers use 'startdate_active', 'startdate_late', 
    # 'startdate_very_late', and 'enddate' in the url
    startdate_active, startdate_late, startdate_very_late, enddate = \
        get_dates_reports(request, 30, 60, 90)
    
    try:
        case = Case.objects.get(domain=domain)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    
    data_by_chw = {}
    case_data = case.get_all_data_maps()
    # organize data by chw id -- this currently only works for pathfinder
    for id, map in case_data.items():
        chw_id = id.split("|")[0]
        if not chw_id in data_by_chw:
            data_by_chw[chw_id] = {}
        data_by_chw[chw_id][id] = map
        
    all_data=get_active_open_by_chw(data_by_chw, startdate_active)
                
    return render_to_string("custom/all/chw_summary.html", 
                            {
                             "all_data": all_data})

def get_active_open_by_chw(data_by_chw, startdate_active):
    all_data = []
    for chw_id, chw_data in data_by_chw.items():
        count_of_open = 0
        count_of_active = 0
        chw_name = ""
        for id, map in chw_data.items():
            form_type_to_date = {'open': datetime(2000, 1, 1), 'close': 
                                 datetime(2000, 1, 1), 'follow': datetime(2000, 1, 1)}
            for form_id, form_info in map.items():
                cfi = CaseFormIdentifier.objects.get(form_identifier=form_id.id)
                form_type = cfi.form_type
                if len(form_info) > 0:
                    # I'm assuming here that the first form in the list is the 
                    # most recently submitted form. I'm also assuming that all 
                    # the forms in this case will have the same chw name 
                    # (since they all have the same chw id)
                    form = form_info[0]
                    chw_name = form["meta_username"]
                    timeend = form["meta_timeend"]
                    # for each form type get the date of the most recently 
                    # submitted form
                    if timeend > form_type_to_date[form_type]:
                        form_type_to_date[form_type] = timeend
            # if the most recent open form was submitted more recently than the 
            # most recent close form then this case is open
            if form_type_to_date['open'] > form_type_to_date['close']:
                count_of_open += 1
                if datetime.date(form_type_to_date['open']) > startdate_active or \
                    datetime.date(form_type_to_date['follow']) > startdate_active:
                    count_of_active += 1
        data_to_display = {}
        data_to_display["chw"]=chw_id
        data_to_display["chw_name"]=chw_name
        data_to_display["active"]=count_of_active
        data_to_display["open"]=count_of_open
        all_data.append(data_to_display.copy()) 
    return all_data
