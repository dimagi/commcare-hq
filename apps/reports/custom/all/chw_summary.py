from datetime import datetime, timedelta

from django.template.loader import render_to_string

from xformmanager.models import Metadata
from graphing.dbhelper import DbHelper
from hq.utils import get_dates_reports

from hq.models import Domain, Organization, ReporterProfile
from apps.reports.models import Case, CaseFormIdentifier
from shared import get_data_by_chw, only_follow, referral_late

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
    all_data = {}
    all_data['domain'] = domain.id
    all_data['enddate'] = str(enddate.month) + "/" + str(enddate.day) + "/" +\
         str(enddate.year)
    all_data['startdate_active'] = str(active.month) + "/" + str(active.day) +\
        "/" + str(active.year)
    all_data['data'] = get_active_open_by_chw(data_by_chw, active, enddate)
    return render_to_string("custom/all/chw_summary.html", 
                            {
                             "all_data": all_data})

def get_active_open_by_chw(data_by_chw, active, enddate):
    data = []
    for chw_id, chw_data in data_by_chw.items():
        counts = get_counts(chw_data, active, enddate, 0, 0, 0, 0, 0, [], '')
        
        percentage = get_percentage(counts['open'], counts['active'])
        if percentage >= 90: over_ninety = True
        else: over_ninety = False
        avg_late = get_avg_late(counts['days_late']) 
        data.append({'chw': chw_id, 'chw_name': counts['chw_name'], 'active':
                    counts['active'], 'open': counts['open'], 'percentage':
                    percentage, 'last_week': counts['last_week'], 'avg_late': 
                    avg_late, 'over_ninety': over_ninety, 'reg_late': 
                    counts['reg_late'], 'ref_late': counts['ref_late']})
    return data

def get_counts(chw_data, active, enddate, num_open, num_active, num_last_week,
               num_ref_late, num_reg_late, days_late_list, chw_name):
    ''' Gets the counts of different status cases and other information
    about this chw'''
    for id, map in chw_data.items():
        (chw_name, form_type_to_date, last_week) = \
            get_form_type_to_date(map, enddate)
        num_last_week += last_week
        # if the most recent open form was submitted more recently than  
        # the most recent close form then this case is open
        if form_type_to_date['open'] > form_type_to_date['close'] or \
            only_follow(form_type_to_date):
            num_open += 1
            if datetime.date(form_type_to_date['open']) >= active or \
                datetime.date(form_type_to_date['follow']) >= active:
                if referral_late(form_type_to_date, enddate, 3):
                    num_ref_late += 1
                else:
                    num_active += 1
            else:
                if referral_late(form_type_to_date, enddate, 3):
                    num_ref_late += 1
                else:
                    days_late = get_days_late(form_type_to_date, active)
                    days_late_list.append(days_late)
                    num_reg_late += 1
    return {'active': num_active, 'open': num_open, 'last_week': num_last_week,
            'reg_late': num_reg_late, 'ref_late': num_ref_late, 'days_late':
            days_late_list, 'chw_name': chw_name}

def get_form_type_to_date(map, enddate):
    ''' Gives the chw name and for each form type, the date of the most 
    recently submitted form'''
    mindate = datetime(2000, 1, 1)
    last_week = 0
    form_type_to_date = {'open': mindate, 'close': mindate, 'follow': mindate,
                         'referral': mindate}
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