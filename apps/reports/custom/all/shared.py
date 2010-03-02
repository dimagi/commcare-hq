from datetime import datetime
from apps.reports.models import CaseFormIdentifier
    
def get_data_by_chw(case):
    ''' Given a case return the data organized by chw id'''
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
    return data_by_chw

def get_case_info(context, chw_data, enddate, active):
    ''' Gives information about each case of a chw'''
    all_data = []
    for id, map in chw_data.items():
        form_dates = []
        mindate = datetime(2000, 1, 1)
        fttd = {'open': mindate, 'close': mindate, 'follow': mindate, 
                'referral': mindate}
        for form_id, form_info in map.items():
            form_type = CaseFormIdentifier.objects.get(form_identifier=
                                                       form_id.id).form_type
            for form in form_info:
                context['chw_name'] = form["meta_username"]
                timeend = form["meta_timeend"]
                if datetime.date(timeend) < enddate:
                    form_dates.append(timeend)
                if timeend > fttd[form_type] and enddate > datetime.date(
                                                                    timeend):
                    fttd[form_type] = timeend
        status = get_status(fttd, active, enddate)
        if not len(form_dates) == 0:
            all_data.append({'case_id': id.split("|")[1], 'total_visits': 
                             len(form_dates), 'start_date': 
                             get_first(form_dates), 'last_visit': 
                             get_last(form_dates), 'status': status})
    context['all_data'] = all_data

def get_counts(current_count, excused_count, late_count, verylate_count,
                open_count, closed_count, chw_data, active, late, enddate):
    ''' Returns the counts of clients in different states (active, late,
    very late, open, closed) and the chw name'''
    mintime = datetime(1000, 1, 1)
    chw_name = ""
    for id, map in chw_data.items():
        (chw_name, form_type_to_date) = get_form_type_to_date(map, enddate,
                                                              mintime)
        if form_type_to_date['open'] > form_type_to_date['close']:
            open_count += 1
            all_types = ['open', 'follow', 'follow_current', 'follow_excused']
            no_excused = ['open', 'follow', 'follow_current']
            most_recent_all = get_most_recent(form_type_to_date, all_types)
            most_recent_no_excused = get_most_recent(form_type_to_date, 
                                                 no_excused)
            if most_recent_no_excused > active:
                current_count += 1
            elif datetime.date(form_type_to_date['follow_excused']) > active:
                excused_count += 1
            elif most_recent_all > late:
                late_count += 1
            elif most_recent_all <= late:
                verylate_count += 1
        elif form_type_to_date['close'] > mintime:
            closed_count += 1
    return {'current': current_count, 'excused': excused_count,
            'late': late_count, 'vlate': verylate_count, 
            'open': open_count, 'closed': closed_count, 
            'chw_name': chw_name}

def get_form_type_to_date(map, enddate, mintime):
    ''' For the forms in a case, returns the most recent date a form was
    submitted for each form type. Also the chw_name for the case'''
    form_type_to_date = {'open': mintime, 'close': mintime, 'follow': mintime,
                         'follow_current': mintime, 'follow_excused': mintime}
    chw_name = ""
    for form_id, form_info in map.items():
        cfi = CaseFormIdentifier.objects.get(form_identifier=form_id.id)
        form_type = cfi.form_type
        for form in form_info:
            timeend = form["meta_timeend"]
            chw_name = form["meta_username"]
            if form_type == 'follow':
                available = get_value(form, '_available')
                if available == '1':
                    form_type = 'follow_current'
                else:
                    form_type = 'follow_excused'
            if timeend > form_type_to_date[form_type] and enddate > \
                datetime.date(timeend):
                form_type_to_date[form_type] = timeend
            if form_type == 'follow_current' or form_type == 'follow_excused':
                form_type = 'follow'
    return (chw_name, form_type_to_date)
    
def get_most_recent(form_type_to_date, keys):
    ''' Given a dictionary of form types to dates, return the most
        recent of those dates'''
    most_recent = form_type_to_date[keys[0]]
    for key in keys:
        if form_type_to_date[key] > most_recent:
            most_recent = form_type_to_date[key]
    return datetime.date(most_recent)

def get_value(form, search_term):
    ''' Given a dictionary of column names to values and a search 
    term, return the value of the column name that ends with that 
    search term. If a key ending in that search term is not found, 
    return an empty string'''
    for key in form.keys():
        if key.endswith(search_term):
            return form[key]
    return ''

def get_first(form_dates):
    ''' Given a list of dates return the first one'''
    if len(form_dates) == 0:
        return ""
    first = form_dates[0]
    for date in form_dates:
        if date < first:
            first = date
    return first

def get_last(form_dates):
    ''' Given a list of dates return the last one'''
    if len(form_dates) == 0:
        return ""
    last = form_dates[0]
    for date in form_dates:
        if date > last:
            last = date
    return last

def get_status(fttd, active, enddate):
    ''' Returns whether active, late, or closed'''
    if fttd['open'] > fttd['close'] or only_follow(fttd):
        if datetime.date(fttd['open']) >= active or datetime.date(
                                                    fttd['follow']) >= active:
            if referral_late(fttd, enddate, 3):
                return 'Late (Referral)'
            else:
                return 'Active'
        else:
            if referral_late(fttd, enddate, 3):
                return 'Late (Referral)'
            else:
                return 'Late (Routine)'
    else:
        return 'Closed'
    
def referral_late(form_type_to_date, enddate, days_late):
    ''' Was the last form submitted a referral form and has it 
    been more than 3 days since that submission'''
    referral = form_type_to_date['referral']
    if form_type_to_date['open'] > referral:
        return False
    elif form_type_to_date['follow'] > referral:
        return False
    elif form_type_to_date['close'] > referral:
        return False
    else:
        time_diff = enddate - datetime.date(referral)
        if time_diff.days > days_late:
            return True
        else:
            return False

def only_follow(fttd):
    ''' for cases where there was no open form but there was a follow form'''
    mindate = datetime(2000, 1, 1)
    if fttd['open'] == mindate and fttd['follow'] > mindate:
        return True
    else:
        return False