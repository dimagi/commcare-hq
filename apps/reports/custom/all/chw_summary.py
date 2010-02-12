from datetime import datetime, timedelta

from django.template.loader import render_to_string

from xformmanager.models import Metadata
from graphing.dbhelper import DbHelper
from hq.utils import get_dates_reports

from hq.models import Domain, Organization, ReporterProfile
from apps.reports.models import Case, CaseFormIdentifier
from shared import get_data_by_chw

def chw_summary(request, domain=None):
    '''The chw_summary report'''
    if not domain:
        domain = request.extuser.domain
    # to configure these numbers use 'startdate_active', 'startdate_late', 
    # and 'enddate' in the url
    active, late, enddate = get_dates_reports(request, 30, 90)
    try:
        case = Case.objects.get(domain=domain)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    
    data_by_chw = get_data_by_chw(case)
    all_data=get_active_open_by_chw(data_by_chw, active, enddate)
    return render_to_string("custom/all/chw_summary.html", 
                            {
                             "all_data": all_data})

def get_active_open_by_chw(data_by_chw, active, enddate):
    all_data = []
    for chw_id, chw_data in data_by_chw.items():
        count_of_open = 0
        count_of_active = 0
        count_last_week = 0
        days_late_list = []
        chw_name = ""
        for id, map in chw_data.items():
            (chw_name, form_type_to_date, last_week) = \
                get_form_type_to_date(map, enddate)
            count_last_week += last_week
            # if the most recent open form was submitted more recently than  
            # the most recent close form then this case is open
            if form_type_to_date['open'] > form_type_to_date['close'] or \
                only_follow(form_type_to_date):
                count_of_open += 1
                if datetime.date(form_type_to_date['open']) >= active or \
                    datetime.date(form_type_to_date['follow']) >= active:
                    count_of_active += 1
                else:
                    days_late = get_days_late(form_type_to_date, active)
                    days_late_list.append(days_late)
        percentage = get_percentage(count_of_open, count_of_active)
        avg_late = get_avg_late(days_late_list)
        data_to_display = {'chw': chw_id, 'chw_name': chw_name, 'active': 
                           count_of_active, 'open': count_of_open, 
                           'percentage': percentage, 'last_week': 
                           count_last_week, 'avg_late': avg_late}
        all_data.append(data_to_display.copy()) 
    return all_data

def get_form_type_to_date(map, enddate):
    ''' Gives the chw name and for each form type, the date of the most 
    recently submitted form'''
    mindate = datetime(2000, 1, 1)
    last_week = 0
    form_type_to_date = {'open': mindate, 'close': mindate, 'follow': mindate}
    for form_id, form_info in map.items():
        cfi = CaseFormIdentifier.objects.get(form_identifier=form_id.id)
        form_type = cfi.form_type
        for form in form_info:
            # I'm assuming that all the forms in this case will have 
            # the same chw name (since they all have the same chw id)
            chw_name = form["meta_username"]
            timeend = form["meta_timeend"]
            time_diff = enddate - datetime.date(timeend)
            if time_diff <= timedelta(days=7) and time_diff >= timedelta(days=0):
                last_week += 1
            # for each form type get the date of the most recently 
            # submitted form
            if timeend > form_type_to_date[form_type] and enddate > \
                datetime.date(timeend):
                form_type_to_date[form_type] = timeend
    return (chw_name, form_type_to_date, last_week)

def get_days_late(form_type_to_date, active):
    '''Returns the number of days past the active date of the most recent form'''
    most_recent = form_type_to_date['follow']
    if form_type_to_date['open'] > most_recent:
        most_recent = form_type_to_date['open']
    time_diff = active - datetime.date(most_recent)
    return time_diff.days

def get_avg_late(days_late_list):
    ''' given a list of days late, return the average number of days'''
    count = 0
    sum = 0
    for days_late in days_late_list:
        count += 1
        sum += days_late
    if not count == 0:
        return sum/count
    else:
        return 0

def get_percentage(count_of_open, count_of_active):
    if not count_of_open == 0:
        return (count_of_active * 100)/count_of_open
    else:
        return 0
    
def only_follow(fttd):
    ''' for cases where there was no open form but there was a follow form'''
    mindate = datetime(2000, 1, 1)
    if fttd['open'] == mindate and fttd['follow'] > mindate:
        return True
    else:
        return False