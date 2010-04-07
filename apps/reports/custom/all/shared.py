from datetime import datetime
from reports.models import CaseFormIdentifier, Case
from reports.custom.pathfinder import ProviderSummaryData, WardSummaryData, HBCMonthlySummaryData
import calendar
from phone.models import PhoneUserInfo

def get_ward_summary_data(startdate, enddate, month, year, ward):
    context = {}
    case_name = "Pathfinder_1" 
    try:
        case = Case.objects.get(name=case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    data_by_chw = get_data_by_chw(case)
    chw_data_list = []
    for chw_id, chw_data in data_by_chw.items():
        chw_obj = WardSummaryData(case, chw_id, chw_data, startdate, enddate)
        if chw_obj.ward == ward:
            chw_data_list.append(chw_obj)
    context["all_data"] = chw_data_list
    context["year"] = year
    context["month"] = calendar.month_name[month]
    context["month_num"] = month
    context["ward"] = ward
    return context
    
def get_provider_summary_data(startdate, enddate, month, year, provider):
    context = {}
    userinfo = None
    puis = PhoneUserInfo.objects.all()
    for pui in puis:
        if provider == pui.username + pui.phone.device_id:
            userinfo = pui
    additional_data = userinfo.additional_data
    case_name = "Pathfinder_1"    
    try:
        case = Case.objects.get(name=case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    data_by_chw = get_data_by_chw(case)
    chw_data = {}
    if provider in data_by_chw:
        chw_data = data_by_chw[provider]
    client_data_list = []
    for client_id, client_data in chw_data.items():
        client_obj = ProviderSummaryData(case, client_id, client_data, 
                                         startdate, enddate)
        if client_obj.num_visits != 0:
            client_data_list.append(client_obj)

    context["all_data"] = client_data_list
    context["month"] = calendar.month_name[month]
    context["month_num"] = month
    context["year"] = year
    context["num"] = provider
    context["prov_name"] = userinfo.username
    for key in additional_data:
        context[key] = additional_data[key] #TODO: change in templates to match what joachim says
    return context

def get_hbc_summary_data(startdate, enddate, month, year, ward):
    context = {}
    case_name = "Pathfinder_1" 
    try:
        case = Case.objects.get(name=case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    data_by_chw = get_data_by_chw(case)
    chw_obj = HBCMonthlySummaryData(case, data_by_chw, startdate, enddate, ward)
    context["all_data"] = chw_obj
    context["month"] = calendar.month_name[month]
    context["month_num"] = month
    context["year"] = year
    context["ward"] = ward
    return context

def get_ward_summary_headings():
    ''' Gets headers to use in csv and pdf files'''
    all_data = []
    all_data.append(['', '', '', '', '', 'Type of Patient visited', '', '',
                     '', '', '', '', '', '', '', '', '', '', '', '' ,'', '',
                     '', '', '', '', '', '', '', '', '', '', ''])
    all_data.append(['', '', '', '', '', 'New', '', '', '', 'Existing', '',
                     '', '', 'Age', '', '', '', 'Deaths', '', '', '',
                     'Transfer', '', '', '', 'Type of Referrals', '', '', '',
                     '', '', '', 'confirmed referrals for this month'])
    all_data.append(['Region', 'District', 'Ward', 'Provider name', 
                     'Provider ID', 'PLWHAs', '', 'CIP', '', 'PLWHAs', '',
                     'CIP', '', '>18yrs', '', '<=18yrs', '', 'PLWHAs', '',
                     'CIP', '', 'PLWHAs', '', 'CIP', '', 'VCT', 'OIS', 'CTC',
                     'PMTCT', 'FP', 'SG', 'TB', ''])
    all_data.append(['', '', '', '', '', 'M', 'F', 'M', 'F', 'M', 'F', 'M',
                     'F', 'M', 'F', 'M', 'F', 'M', 'F', 'M', 'F', 'M', 'F',
                     'M', 'F', '', '', '', '', '', '', '', ''])
    return all_data

def get_hbc_monthly_display(chw_obj):
    ''' Gets headers and data to use in csv and pdf files'''
    table2 = []
    table2.append(['', 'Total', '', 'Less than 15', '', '15 to 24', '',
                   '25-49', '', '50 and above', ''])
    table2.append(['', 'M', 'F', 'M', 'F', 'M', 'F', 'M', 'F', 'M', 'F'])
    table2.append(['1. Number of New Clients enrolled this month', 
                chw_obj.new_total_m, chw_obj.new_total_f, chw_obj.new_0_14_m,
                chw_obj.new_0_14_f, chw_obj.new_15_24_m, chw_obj.new_15_24_f,
                chw_obj.new_25_49_m, chw_obj.new_25_49_f, chw_obj.new_50_m,
                chw_obj.new_50_f])
    table2.append(['2. New and continuing clients receiving services this month',
                chw_obj.all_total_m, chw_obj.all_total_f, '', '', '', '', '',
                '', '', ''])
    table2.append(['   HIV status', '', '', '', '', '', '', '', '', '', ''])
    table2.append(['       Positive', chw_obj.positive_m, chw_obj.positive_f,
                   '', '', '', '', '', '', '', ''])
    table2.append(['       Negative', chw_obj.negative_m, chw_obj.negative_f,
                   '', '', '', '', '', '', '', ''])
    table2.append(['       Unknown', chw_obj.unknown_m, chw_obj.unknown_f, '',
                   '', '', '', '', '', '', ''])
    table2.append(['   CTC enrollment status', '', '', '', '', '', '', '', '',
                     '', ''])
    table2.append(['       Enrolled in CTC but not on ARVs', chw_obj.ctc_m, 
                     chw_obj.ctc_f, '', '', '', '', '', '', '', ''])
    table2.append(['       Enrolled in CTC and on ARVs', chw_obj.ctc_arv_m,
                     chw_obj.ctc_arv_f, '', '', '', '', '', '', '', ''])
    table2.append(['       Not enrolled in CTC', chw_obj.no_ctc_m, 
                     chw_obj.no_ctc_f, '', '', '', '', '', '', '', ''])
    table2.append(['3. Number of clients ever enrolled in HBC', 
                     chw_obj.enrolled_m, chw_obj.enrolled_f, '', '', '', '',
                      '', '', '', ''])
    return table2

def get_hbc_monthly_display_second(chw_obj):
    ''' Gets the headers and data to use in the second table in 
    csv and pdf files'''
    table3 = []
    table3.append(['', 'Died', 'Lost', 'Transferred to other HBC services', 
                'Migrated', 'No longer in need of services', 'Opted out', 
                'Total'])
    table3.append(['4. Number of clients no longer receiving services', 
                chw_obj.died, chw_obj.lost, chw_obj.transferred, 
                chw_obj.migrated, chw_obj.no_need, chw_obj.opt_out, 
                chw_obj.total_no_services])
    return table3

def get_provider_summary_headers():
    ''' Gets the headers to use in the csv and pdf files'''
    return ['HBC Patient Code', 'Age', 'Sex', 'HBC Status', 
            'Number of visits during', 'HIV status', 'Functional status',
            'CTC status', 'CTC Number', 'Material items provided', 
            'Services provided', 'Referrals made', 'Referrals completed']
    
def get_data_by_chw(case):
    ''' Given a case return the data organized by chw id'''
    data_by_chw = {}
    case_data = case.get_all_data_maps()
    # organize data by chw id -- this currently only works for pathfinder
    for id, map in case_data.items():
        index = id.find('|')
        if index != -1 and index != 0:
            all_ids = id.split("|")
            if len(all_ids) == 3:
                chw_id = all_ids[0] + all_ids[1]
                id = all_ids[2]
            else:
                chw_id = all_ids[0]
                id = all_ids[1]
            if not chw_id in data_by_chw:
                data_by_chw[chw_id] = {}
            data_by_chw[chw_id][id] = map
    return data_by_chw

def get_wards():
    ''' Get a list of all wards'''
    wards = []
    puis = PhoneUserInfo.objects.all()
    for pui in puis:
        additional_data = pui.additional_data
        if "ward" in additional_data:
            ward = additional_data["ward"]
            if not ward in wards and ward != None:
                wards.append(ward)
    return wards

def get_mon_year(request):
    ''' Given a request returns the month and year included in it'''
    year = ""
    month = ""
    if request:
        for item in request.POST.items():
            if item[0] == 'year':
                year = int(item[1])
            if item[0] == 'month':
                month = int(item[1])
    
    startdate = datetime(year, month, 01).date()
    nextmonth = month + 1
    if nextmonth == 13:
        nextmonth = 1
    enddate = datetime(year, nextmonth, 01).date()
    return (month, year, startdate, enddate)

def get_start_end(month, year):
    ''' Given a month and year, returns the first date of the month and the
    first day of the next month'''
    month = int(month)
    year = int(year)
    startdate = datetime(year, month, 01).date()
    nextmonth = month + 1
    if nextmonth == 13:
        nextmonth = 1
    enddate = datetime(year, nextmonth, 01).date()
    return (startdate, enddate)

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