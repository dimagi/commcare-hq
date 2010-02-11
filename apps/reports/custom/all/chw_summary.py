from datetime import datetime, timedelta

from django.template.loader import render_to_string

from xformmanager.models import Metadata
from graphing.dbhelper import DbHelper
from hq.utils import get_dates_reports

from domain.models import Domain
from hq.models import Organization, ReporterProfile
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
        index = id.find('|')
        if index != -1:
            chw_id = id.split("|")[0]
            if not chw_id in data_by_chw:
                data_by_chw[chw_id] = {}
            data_by_chw[chw_id][id] = map
        
    all_data=get_active_open_by_chw(data_by_chw, startdate_active, enddate)
                
    return render_to_string("custom/all/chw_summary.html", 
                            {
                             "all_data": all_data})

def get_active_open_by_chw(data_by_chw, active, enddate):
    all_data = []
    for chw_id, chw_data in data_by_chw.items():
        count_of_open = 0
        count_of_active = 0
        chw_name = ""
        for id, map in chw_data.items():
            (chw_name, form_type_to_date) = get_form_type_to_date(map, enddate)
            # if the most recent open form was submitted more recently than  
            # the most recent close form then this case is open
            if form_type_to_date['open'] > form_type_to_date['close']:
                count_of_open += 1
                if datetime.date(form_type_to_date['open']) > active or \
                    datetime.date(form_type_to_date['follow']) > active:
                    count_of_active += 1
        data_to_display = {'chw': chw_id, 'chw_name': chw_name, 'active': 
                           count_of_active, 'open': count_of_open}
        all_data.append(data_to_display.copy()) 
    return all_data

def get_form_type_to_date(map, enddate):
    ''' Gives the chw name and for each form type, the date of the most 
    recently submitted form'''
    mindate = datetime(2000, 1, 1)
    form_type_to_date = {'open': mindate, 'close': mindate, 'follow': mindate}
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
            if timeend > form_type_to_date[form_type] and enddate > \
                datetime.date(timeend):
                form_type_to_date[form_type] = timeend
    return (chw_name, form_type_to_date)