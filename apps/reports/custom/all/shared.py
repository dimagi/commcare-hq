from datetime import datetime, timedelta
from reports.models import CaseFormIdentifier, Case
from reports.custom.pathfinder import ProviderSummaryData, WardSummaryData, HBCMonthlySummaryData
import calendar
from phone.models import PhoneUserInfo, Phone
from StringIO import StringIO
try:
    from reportlab.pdfgen import canvas
    from reportlab.platypus import *
    from reportlab.lib.pagesizes import portrait
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import *
except ImportError:
    # reportlab isn't installed.  some views will fail but this is better
    # than bringing down all of HQ
    pass

def get_ward_summary_pdf(startdate, enddate, month, year, ward, doc):
    ''' Builds pdf document for ward summary report'''
    chw_data_list = get_ward_chw_data_list(startdate, enddate, ward)
    doc.pagesize = (841.88976377952747, 595.27559055118104) # landscape
    doc.title = "Ward Summary Report"
    elements = []
    
    ps = ParagraphStyle(name='Normal', alignment=TA_CENTER) 
    para = Paragraph('Ward Summary Report<br/>Month: %s<br/>Year: %s'% 
                     ( calendar.month_name[int(month)], year), ps)
    elements.append(para)
    all_data = []
    
    style = ParagraphStyle(name='header', fontName='Times-Bold', fontSize=6)
    for line in get_ward_summary_headings():
        headers = []
        for entry in line:
            para = Paragraph(entry, style)
            headers.append(para)
        all_data.append(headers)
    
    # maybe make these paragraphs so they wrap too?
    for chw_data in chw_data_list:
        all_data.append(chw_data.data)
    colwidths = [40, 40, 40, 40, 40, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17,
                 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 22, 22, 22, 30, 22,
                 22, 22, 34]
    table = Table(all_data, colwidths, repeatRows=4, splitByRow=0)
    ts = TableStyle([('FONTSIZE', (0, 0), (-1, -1), 6),
                    ('SPAN', (5, 0), (12, 0)), ('SPAN', (5, 1), (8, 1)),
                    ('SPAN', (5, 2), (6, 2)), ('SPAN', (7, 2), (8, 2)),
                    ('SPAN', (9, 1), (12, 1)), ('SPAN', (9, 2), (10, 2)),
                    ('SPAN', (11, 2), (12, 2)), ('SPAN', (13, 1), (16, 1)),
                    ('SPAN', (13, 2), (14,2)), ('SPAN', (15, 2), (16, 2)),
                    ('SPAN', (17, 1), (20, 1)), ('SPAN', (17, 2), (18, 2)),
                    ('SPAN', (19, 2), (20, 2)), ('SPAN', (21, 1), (24, 1)),
                    ('SPAN', (21, 2), (22, 2)), ('SPAN', (23, 2), (24, 2)),
                    ('SPAN', (25, 1), (31, 1)), ('SPAN', (32, 1), (32, 2)),
                    ('INNERGRID', (0,0), (-1,-1), 0.25, colors.black),
                    ('BOX', (0,0), (-1,-1), 0.25, colors.black)])
    table.setStyle(ts)
    elements.append(table)
    doc.build(elements)
    
def get_provider_summary_pdf(month, year, chw_id, client_data_list, doc):
    ''' Builds pdf document for summary by provider report'''
    doc.pagesize = (841.88976377952747, 595.27559055118104) # landscape
    doc.title = "Home Based Care Patients Summary for Month"
    elements = []
    
    ps = ParagraphStyle(name='Normal', alignment=TA_CENTER) 
    para = Paragraph('Home Based Care Patients Summary for Month', ps)
    elements.append(para)
    
    data = get_user_data(chw_id)
    
    provider_data = get_provider_data_list(data, month, year)
    for row in provider_data:
        row_table = Table([row])
        row_table.hAlign='LEFT'
        row_table.setStyle(TableStyle([('FONTNAME', (0, 0), (0, 0), 
                                        'Times-Bold')]))
        if len(row) > 2:
            row_table.setStyle(TableStyle([('FONTNAME', (2, 0), (2, 0), 
                                        'Times-Bold')]))
        if len(row) > 4:
            row_table.setStyle(TableStyle([('FONTNAME', (4, 0), (4, 0), 
                                        'Times-Bold')]))
        elements.append(row_table)
    
    all_data = []
    headers = []
    style_h = ParagraphStyle(name='header', fontName='Times-Bold', fontSize=7)
    for header in get_provider_summary_headers():
        para = Paragraph(header, style_h)
        headers.append(para)
    all_data.append(headers)
    style_r = ParagraphStyle(name='header', fontName='Times-Roman', fontSize=7)
    for chw_data in client_data_list:
        datas = []
        for data in chw_data.data:
            para = Paragraph(str(data), style_r)
            datas.append(para)
        all_data.append(datas)
    table = Table(all_data, repeatRows=1, splitByRow=1)
    table.setStyle(TableStyle([('INNERGRID', (0,0), (-1,-1), 0.25, 
                                colors.black),
                               ('BOX', (0,0), (-1,-1), 0.25, colors.black)]))

    elements.append(table)
    doc.build(elements)
    
def get_hbc_monthly_pdf(month, year, chw_obj, ward, doc):
    ''' Builds pdf document for hbc monthly summary report'''
    doc.title = "Home Based Care Monthly Summary Report"
    elements = []
    
    ps = ParagraphStyle(name='Normal', alignment=TA_CENTER) 
    para = Paragraph('Home Based Care Monthly Summary Report<br/>Ward: %s<br/>Month: %s<br/>Year: %s<br/><br/>'% 
                     ( ward, calendar.month_name[int(month)], year), ps)
    elements.append(para)
    
    table1 = []
    table1.append(['Number of providers - who reported this month:',
                chw_obj.providers_reporting, 
                '- who did not report this month:',
                chw_obj.providers_not_reporting])
    t1 = Table(table1)
    t1.setStyle(TableStyle([('FONTSIZE', (0, 0), (-1, -1), 8),
                            ('FONTNAME', (2, 0), (2, 0), 'Times-Bold'),
                            ('FONTNAME', (0, 0), (0, 0), 'Times-Bold'),
                            ('INNERGRID', (0,0), (-1,-1), 0.25, colors.black),
                            ('BOX', (0,0), (-1,-1), 0.25, colors.black)]))
    t1.hAlign='LEFT'
    elements.append(t1)
    elements.append(Paragraph('<br/>', ps))

    table2 = get_hbc_monthly_display(chw_obj)
    t2 = Table(table2)
    t2.setStyle(TableStyle([('FONTSIZE', (0, 0), (-1, -1), 8),
                            ('FONTNAME', (0, 0), (-1, 1), 'Times-Bold'),
                            ('FONTNAME', (0, 4), (0, 4), 'Times-Italic'),
                            ('FONTNAME', (0, 8), (0, 8), 'Times-Italic'),
                            ('SPAN', (1, 0), (2, 0)), #Total
                            ('SPAN', (3, 0), (4, 0)), #Less than 15
                            ('SPAN', (5, 0), (6, 0)), #15-24
                            ('SPAN', (7, 0), (8, 0)), #25-49
                            ('SPAN', (9, 0), (10, 0)), #50 and above
                            ('INNERGRID', (0,0), (-1,-1), 0.25, colors.black),
                            ('BOX', (0,0), (-1,-1), 0.25, colors.black)]))
    t2.hAlign = 'LEFT'
    elements.append(t2)
    elements.append(Paragraph('<br/>', ps))
    
    table3 = []
    style_h = ParagraphStyle(name='style', fontName='Times-Bold', fontSize=8)
    style_r = ParagraphStyle(name='style', fontName='Times-Roman', fontSize=8)
    lines = get_hbc_monthly_display_second(chw_obj)
    headers = []
    for entry in lines[0]:
        para = Paragraph(str(entry), style_h)
        headers.append(para)
    table3.append(headers)
    headers = []
    for entry in lines[1]:
        para = Paragraph(str(entry), style_r)
        headers.append(para)
    table3.append(headers)
    t3 = Table(table3)
    t3.setStyle(TableStyle([('INNERGRID', (0,0), (-1,-1), 0.25, colors.black),
                            ('BOX', (0,0), (-1,-1), 0.25, colors.black)]))
    t3.hAlign='LEFT'
    elements.append(t3)
    doc.build(elements)

def get_ward_summary_data(startdate, enddate, month, year, ward):
    context = {}
    chw_data_list = get_ward_chw_data_list(startdate, enddate, ward)
    context["all_data"] = chw_data_list
    context["year"] = year
    context["month"] = calendar.month_name[month]
    context["month_num"] = month
    context["ward"] = ward
    return context

def get_ward_chw_data_list(startdate, enddate, ward):
    ''' Get a list of WardSummaryData's for the given ward'''
    chw_data_list = []
    
    case_name = "Pathfinder_1" 
    try:
        case = Case.objects.get(name=case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    data_by_chw = get_data_by_chw(case)
    
    puis = PhoneUserInfo.objects.all()
    if puis != None:
        for pui in puis:
            chw_id = pui.username + pui.phone.device_id
            chw_data = None
            if chw_id in data_by_chw:
                chw_data = data_by_chw[chw_id]
            chw_obj = WardSummaryData(case, chw_id, chw_data, startdate, enddate)
            if chw_obj.ward == ward:
                chw_data_list.append(chw_obj)
    return chw_data_list
    
def get_provider_summary_data(startdate, enddate, month, year, provider):
    context = {}
    userinfo = None
    puis = PhoneUserInfo.objects.all()
    if puis != None:
        for pui in puis:
            if provider == pui.username + pui.phone.device_id:
                userinfo = pui
    additional_data = None
    if userinfo != None:
        additional_data = userinfo.additional_data
    case_name = "Pathfinder_1"    
    client_data_list = get_provider_data_by_case(case_name, provider, startdate, enddate)
    context["all_data"] = client_data_list
    context["month"] = calendar.month_name[month]
    context["month_num"] = month
    context["year"] = year
    context["num"] = provider
    if userinfo != None:
        context["prov_name"] = userinfo.username
    if additional_data != None:
        for key in additional_data:
            context[key] = additional_data[key] #TODO: change in templates to match what joachim says
    return context

def get_provider_data_by_case(case_name, provider, startdate, enddate):
    ''' Given a case and provider returns data about each client'''
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
    return client_data_list

def get_hbc_summary_data(startdate, enddate, month, year, ward):
    ''' Gets the data for the hbc monthly summary report given a ward'''
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
    context["month"] = calendar.month_name[int(month)]
    context["month_num"] = month
    context["year"] = year
    context["ward"] = ward
    return context

def get_user_data(chw_id):
    ''' Gets user specific data from PhoneUserInfo'''
    data = {}
    userinfo = None
    puis = PhoneUserInfo.objects.all()
    if puis != None:
        for pui in puis:
            if chw_id == pui.username + pui.phone.device_id:
                data["prov_name"] = pui.username
                userinfo = pui
    if userinfo != None:
        additional_data = userinfo.additional_data
        if additional_data != None:
            for key in additional_data:
                data[key] = additional_data[key]
    return data

def get_provider_data_list(data, month, year):
    ''' Gets the provider specific data arranged properly with headers for the 
    summary by provider report'''
    all_data = []
    
    first_row = ['Region:', '', 'District:', '', 'Ward:', '']
    if 'region' in data:
        first_row[1] = data['region']
    if 'district' in data:
        first_row[3] = data['district']
    if 'ward' in data:
        first_row[5] = data['ward']
    all_data.append(first_row)
    
    all_data.append(['Report for month:', calendar.month_name[int(month)], 'Year:',
                     year])
    
    third_row = ['HBC Provider name:', '', 'HBC Provider number:', '']
    if 'prov_name' in data:
        third_row[1] = data['prov_name']
    if 'hcbpid' in data:
        third_row[3] = data['hcbpid']
    all_data.append(third_row)
    
    return all_data

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
            all_ids = id.split('|')
            if len(all_ids) == 3:
                chw_id = all_ids[0] + all_ids[1]
                id = all_ids[2]
                if not chw_id in data_by_chw:
                    data_by_chw[chw_id] = {}
                data_by_chw[chw_id][id] = map
    return data_by_chw

def get_wards():
    ''' Get a list of all wards'''
    wards = []
    puis = PhoneUserInfo.objects.all()
    if puis != None:
        for pui in puis:
            additional_data = pui.additional_data
            if additional_data != None and "ward" in additional_data:
                ward = additional_data["ward"]
                if ward != None and not ward in wards:
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
                temp_form_type = form_type
                context['chw_name'] = form["meta_username"]
                timeend = form["meta_timeend"]
                if form_type == 'follow':
                    referral = get_value(form, 'referral_id')
                    if referral and referral != '':
                        temp_form_type = 'referral'
                if datetime.date(timeend) < enddate:
                    form_dates.append(timeend)
                if timeend > fttd[temp_form_type] and enddate > datetime.date(
                                                                    timeend):
                    fttd[temp_form_type] = timeend
        status = get_status(fttd, active, enddate)
        if not len(form_dates) == 0:
            all_data.append({'case_id': id, 'total_visits': len(form_dates),
                             'start_date': get_first(form_dates), 
                             'last_visit': get_last(form_dates), 'status': 
                             status})
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
        if datetime.date(fttd['open']) >= active or \
            datetime.date(fttd['follow']) >= active or \
            datetime.date(fttd['referral']) >= active:
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
    if fttd['open'] == mindate and fttd['follow'] > mindate or \
                                    fttd['referral'] > mindate:
        return True
    else:
        return False
    

def get_active_open_by_chw(data_by_chw, active, enddate):
    data = []
    for chw_id, chw_data in data_by_chw.items():
        user_data = get_user_data(chw_id)
        count_of_open = 0
        count_of_active = 0
        count_last_week = 0
        days_late_list = []
        chw_name = ''
        hcbpid = chw_id
        #if 'prov_name' in user_data:
        #    chw_name = user_data['prov_name']
        if 'hcbpid' in user_data:
            hcbpid = user_data['hcbpid']
        mindate = datetime(2000, 1, 1)
        for id, map in chw_data.items():
            (chw_name, form_type_to_date, last_week) = \
                get_form_type_to_date_last_week(map, enddate, mindate)
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
        if percentage >= 90: over_ninety = True
        else: over_ninety = False
        avg_late = get_avg_late(days_late_list) 
        data.append({'chw': chw_id, 'chw_name': chw_name, 'active':
                    count_of_active, 'open': count_of_open, 
                    'percentage': percentage, 'last_week': 
                    count_last_week, 'avg_late': avg_late,
                    'over_ninety': over_ninety})
    return data

def get_form_type_to_date_last_week(map, enddate, mindate):
    ''' Gives the chw name and for each form type, the date of the most 
    recently submitted form. Also the number of forms in the last week'''
    last_week = 0
    chw_name = ''
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
            if time_diff <= timedelta(days=7) and time_diff >= \
                timedelta(days=0):
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