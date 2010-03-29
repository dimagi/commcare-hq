from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect

from rapidsms.webui.utils import render_to_response

from transformers.csv import format_csv 
from models import Case, SqlReport
from xformmanager.models import FormDefModel
from hq.utils import paginate
from domain.decorators import login_and_domain_required

import util
from custom.all.shared import get_data_by_chw, get_case_info, get_mon_year, get_ward_summary_data, get_provider_summary_data, get_hbc_summary_data
from custom.pathfinder import ProviderSummaryData, WardSummaryData, HBCMonthlySummaryData

from StringIO import StringIO
from transformers.csv import UnicodeWriter
import calendar
try:
    from reportlab.pdfgen import canvas
    from reportlab.platypus import *
    from reportlab.lib.pagesizes import portrait
    from reportlab.lib import colors
except ImportError:
    # reportlab isn't installed.  some views will fail but this is better
    # than bringing down all of HQ
    pass



@login_and_domain_required
def reports(request, template_name="list.html"):
    # not sure where this view will live in the UI yet
    context = {}
    context['case_reports'] = Case.objects.filter(domain=request.user.selected_domain)
    context['sql_reports'] = SqlReport.objects.filter(domain=request.user.selected_domain, is_active=True)
    context['custom_reports'] = util.get_custom_reports(request.user.selected_domain)
    if not context['custom_reports'] and not context['sql_reports']\
       and not context['case_reports']:
        return render_to_response(request, 
                                  "domain_not_found.html",
                                  context)
    return render_to_response(request, template_name, context)

@login_and_domain_required
def case_flat(request, case_id, template_name="case_flat.html"):
    '''A flat view of the topmost data for all cases'''
    context = {}
    case = Case.objects.get(id=case_id)
    
    context['cols'] = case.get_column_names()
    
    data = case.get_topmost_data()
    keys = data.keys()
    keys.sort()
    flattened = []
    for key in keys:
        flattened.append(data[key])
    
    
    context['data'] = paginate(request, flattened)    
    context['case'] = case
    
    return render_to_response(request, template_name, context)

    
@login_and_domain_required
def single_case_view(request, case_id, case_instance_id, template_name="single_case.html"):
    '''View for all of a single case's data, broken down by form.'''
    context = {}
    case = Case.objects.get(id=case_id)
    data = case.get_data_for_case(case_instance_id)
    
    context['case_instance_id'] = case_instance_id
    context['case_data'] = data
    context['case'] = case
    
    return render_to_response(request, template_name, context)

@login_and_domain_required
def case_export_csv(request, case_id):
    case = Case.objects.get(id=case_id)
    cols = case.get_column_names()
    data = case.get_topmost_data().values()
    output = StringIO()
    w = UnicodeWriter(output)
    w.writerow(cols)
    for row in data:
        w.writerow(row)
    output.seek(0)
    response = HttpResponse(output.read(),
                        mimetype='application/ms-excel')
    response["content-disposition"] = 'attachment; filename="%s-%s.csv"' % ( case.name, str(datetime.now().date()))
    return response


@login_and_domain_required
def custom_report(request, domain_id, report_name):
    context = {}
    context["report_name"] = report_name
    report_method = util.get_report_method(request.user.selected_domain, report_name)
    if not report_method:
        return render_to_response(request, 
                                  "custom/report_not_found.html",
                                  context)
    context["report_display"] = report_method.__doc__
    context["report_body"] = report_method(request)
    return render_to_response(request, "custom/base.html", context)

@login_and_domain_required
def sql_report(request, report_id, template_name="sql_report.html"):
    '''View a single sql report.'''
    report = SqlReport.objects.get(id=report_id)
    whereclause = util.get_whereclause(request.GET)
    table = report.to_html_table({"whereclause": whereclause})
    return render_to_response(request, template_name, {"report": report, "table": table})

@login_and_domain_required
def sql_report_csv(request, report_id):
    '''View a single sql report.'''
    report = SqlReport.objects.get(id=report_id)
    whereclause = util.get_whereclause(request.GET)
    cols, data = report.get_data({"whereclause": whereclause})
    return format_csv(data, cols, report.title)
    

@login_and_domain_required
def individual_chw(request, domain_id, chw_id, enddate, active):
    '''View the cases of a single chw'''
    context = {}
    enddate = datetime.strptime(enddate, '%m/%d/%Y').date()
    active = datetime.strptime(active, '%m/%d/%Y').date()
    context['chw_id'] = chw_id
    domain = request.extuser.domain
    case = Case.objects.get(domain=domain)
    data_by_chw = get_data_by_chw(case)
    get_case_info(context, data_by_chw[chw_id], enddate, active)
    return render_to_response(request, "custom/all/individual_chw.html", 
                              context)

def sum_provider(request):
    '''View a single provider summary report'''
    provider = None
    if request:
        for item in request.POST.items():
            if item[0] == 'provider':
                provider=item[1]
    (month, year, startdate, enddate) = get_mon_year(request)
    context = get_provider_summary_data(startdate, enddate, month, year, 
                                        provider)
    return render_to_response(request, 
                              "custom/pathfinder/sum_by_provider_report.html",
                              context)

def sum_ward(request):
    '''View the ward summary report'''
    (month, year, startdate, enddate) = get_mon_year(request)
    context = get_ward_summary_data(startdate, enddate, month, year)
    return render_to_response(request, 
                              "custom/pathfinder/ward_summary_report.html", 
                              context)

def hbc_monthly_sum(request):
    ''' View the hbc monthly summary report'''
    (month, year, startdate, enddate) = get_mon_year(request)
    context = get_hbc_summary_data(startdate, enddate, month, year)
    return render_to_response(request, 
                              "custom/pathfinder/hbc_summary_report.html", 
                              context)
    
def ward_sum_csv(request, month, year):
    ''' Creates CSV file of ward summary report'''
    month = int(month)
    year = int(year)
    startdate = datetime(year, month, 01).date()
    nextmonth = month + 1
    if nextmonth == 13:
        nextmonth = 1
    enddate = datetime(year, nextmonth, 01).date()
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
        chw_data_list.append(chw_obj)
    output = StringIO()
    w = UnicodeWriter(output)
    w.writerow(['', '', '', '', '', 'Type of Patient visited'])
    w.writerow(['', '', '', '', '', 'New', '', '', '', 'Existing', '', '', '',
                'Age', '', '', '', 'Deaths', '', '', '', 'Transfer', '', '', 
                '', 'Type of Referrals', '', '', '', '', '', '', 
                'confirmed referrals for this month'])
    w.writerow(['Region', 'District', 'Ward', 'Provider name', 'Provider ID', 
                'PLWHAs', '', 'CIP', '', 'PLWHAs', '', 'CIP', '', '>18yrs', 
                '', '<=18yrs', '', 'PLWHAs', '', 'CIP', '', 'PLWHAs', '', 
                'CIP', '', 'VCT', 'OIS', 'CTC', 'PMTCT', 'FP', 'SG', 'TB'])
    w.writerow(['', '', '', '', '', 'M', 'F', 'M', 'F', 'M', 'F', 'M', 'F', 
                'M', 'F', 'M', 'F', 'M', 'F', 'M', 'F', 'M', 'F', 'M', 'F'])
    for row in chw_data_list:
        w.writerow(row)
    output.seek(0)
    response = HttpResponse(output.read(), mimetype='application/ms-excel')
    response["content-disposition"] = 'attachment; filename="ward_summary_%s-%s.csv"'\
                                        % ( month, year)
    return response

def sum_prov_csv(request, chw_id, month, year):
    ''' Creates CSV file of summary by provider report'''
    case_name = "Pathfinder_1"
    month = int(month)
    year = int(year)
    startdate = datetime(year, month, 01).date()
    nextmonth = month + 1
    if nextmonth == 13:
        nextmonth = 1
    enddate = datetime(year, nextmonth, 01).date()
    
    try:
        case = Case.objects.get(name=case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    data_by_chw = get_data_by_chw(case)
    chw_data = data_by_chw[chw_id]
    client_data_list = []
    for client_id, client_data in chw_data.items():
        client_obj = ProviderSummaryData(case, client_id, client_data, 
                                         startdate, enddate)
        if client_obj.num_visits != 0:
            client_data_list.append(client_obj)
    output = StringIO()
    w = UnicodeWriter(output)
    w.writerow(['HBC Patient Code', 'Age', 'Sex', 'HBC Status', 
                'Number of visits during', 'HIV status', 'Functional status',
                'CTC status', 'CTC Number', 'Material items provided', 
                'Services provided', 'Referrals made', 'Referrals completed'])
    for row in client_data_list:
        w.writerow(row)
    output.seek(0)
    response = HttpResponse(output.read(), mimetype='application/ms-excel')
    response["content-disposition"] = 'attachment; filename="provider_%s_summary_%s-%s.csv"'\
                                        % ( chw_id, month, year)
    return response

def hbc_sum_csv(request, month, year):
    '''Creates csv file of HBC monthly summary report'''
    case_name = "Pathfinder_1" 
    month = int(month)
    year = int(year)
    startdate = datetime(year, month, 01).date()
    nextmonth = month + 1
    if nextmonth == 13:
        nextmonth = 1
    enddate = datetime(year, nextmonth, 01).date()
    
    try:
        case = Case.objects.get(name=case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    data_by_chw = get_data_by_chw(case)
    chw_obj = HBCMonthlySummaryData(case, data_by_chw, startdate, enddate)
    output = StringIO()
    w = UnicodeWriter(output)
    w.writerow(['Number of providers - who reported this month:',
                chw_obj.providers_reporting])
    w.writerow(['- who did not report this month:', 
                chw_obj.providers_not_reporting])
    w.writerow('')
    w.writerow(['', 'Total', '', 'Less than 15', '', '15 to 24', '', '25-49',
                 '', '50 and above'])
    w.writerow(['', 'M', 'F', 'M', 'F', 'M', 'F', 'M', 'F', 'M', 'F'])
    w.writerow(['1. Number of New Clients enrolled this month', 
                chw_obj.new_total_m, chw_obj.new_total_f, chw_obj.new_0_14_m,
                chw_obj.new_0_14_f, chw_obj.new_15_24_m, chw_obj.new_15_24_f,
                chw_obj.new_25_49_m, chw_obj.new_25_49_f, chw_obj.new_50_m,
                chw_obj.new_50_f])
    w.writerow('')
    w.writerow(['2. New and continuing clients receiving services this month',
                chw_obj.all_total_m, chw_obj.all_total_f])
    w.writerow('')
    w.writerow(['HIV status'])
    w.writerow(['Positive', chw_obj.positive_m, chw_obj.positive_f])
    w.writerow(['Negative', chw_obj.negative_m, chw_obj.negative_f])
    w.writerow(['Unknown', chw_obj.unknown_m, chw_obj.unknown_f])
    w.writerow('')
    w.writerow(['CTC enrollment status'])
    w.writerow(['Enrolled in CTC but not on ARVs', chw_obj.ctc_m, 
                chw_obj.ctc_f])
    w.writerow(['Enrolled in CTC and on ARVs', chw_obj.ctc_arv_m,
                chw_obj.ctc_arv_f])
    w.writerow(['Not enrolled in CTC', chw_obj.no_ctc_m, chw_obj.no_ctc_f])
    w.writerow('')
    w.writerow(['3. Number of clients ever enrolled in HBC', 
                chw_obj.enrolled_m, chw_obj.enrolled_f])
    w.writerow('')
    w.writerow('')
    w.writerow(['', 'Died', 'Lost', 'Transferred to other HBC services', 
                'Migrated', 'No longer in need of services', 'Opted out', 
                'Total'])
    w.writerow(['4. Number of clients no longer receiving services', 
                chw_obj.died, chw_obj.lost, chw_obj.transferred, 
                chw_obj.migrated, chw_obj.no_need, chw_obj.opt_out, 
                chw_obj.total_no_services])
    output.seek(0)
    response = HttpResponse(output.read(), mimetype='application/ms-excel')
    response["content-disposition"] = 'attachment; filename="hbc_monthly_summary_%s-%s.csv"'\
                                        % ( month, year)
    return response

def ward_sum_pdf(request, month, year):
    ''' Creates PDF file of ward summary report'''
    month = int(month)
    year = int(year)
    startdate = datetime(year, month, 01).date()
    nextmonth = month + 1
    if nextmonth == 13:
        nextmonth = 1
    enddate = datetime(year, nextmonth, 01).date()
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
        chw_data_list.append(chw_obj)

    response = HttpResponse(mimetype='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=ward_summary_%s-%s.pdf'\
                                        % (month, year)
    doc = SimpleDocTemplate(response)
    doc.pagesize = (841.88976377952747, 595.27559055118104) # portrait
    elements = []
    
    all_data = []
    all_data.append(['', '', '', '', '', 'Type of Patient visited', '', '',
                     '', '', '', '', '', '', '', '', '', '', '', '' ,'', '',
                     '', '', '', '', '', '', '', '', '', '', ''])
    all_data.append(['', '', '', '', '', 'New', '', '', '', 'Existing', '', '', '',
                'Age', '', '', '', 'Deaths', '', '', '', 'Transfer', '', '', 
                '', 'Type of Referrals', '', '', '', '', '', '', 
                'confirmed referrals for this month'])
    all_data.append(['Region', 'District', 'Ward', 'Provider name', 'Provider ID', 
                'PLWHAs', '', 'CIP', '', 'PLWHAs', '', 'CIP', '', '>18yrs', 
                '', '<=18yrs', '', 'PLWHAs', '', 'CIP', '', 'PLWHAs', '', 
                'CIP', '', 'VCT', 'OIS', 'CTC', 'PMTCT', 'FP', 'SG', 'TB', ''])
    all_data.append(['', '', '', '', '', 'M', 'F', 'M', 'F', 'M', 'F', 'M', 'F', 
                'M', 'F', 'M', 'F', 'M', 'F', 'M', 'F', 'M', 'F', 'M', 'F',
                '', '', '', '', '', '', '', ''])
    
    for chw_data in chw_data_list:
        this_list = [chw_data.region, chw_data.district, chw_data.ward, 
                     chw_data.chw_name, chw_data.chw_id, chw_data.new_plha_m, 
                     chw_data.new_plha_f, chw_data.new_cip_m, 
                     chw_data.new_cip_f, chw_data.existing_plha_m, 
                     chw_data.existing_plha_f, chw_data.existing_cip_m, 
                     chw_data.existing_cip_f, chw_data.adult_m, 
                     chw_data.adult_f, chw_data.child_m, chw_data.child_f,
                     chw_data.death_plha_m, chw_data.death_plha_f, 
                     chw_data.death_cip_m, chw_data.death_cip_f,
                     chw_data.transfer_plha_m, chw_data.transfer_plha_f, 
                     chw_data.transfer_cip_m, chw_data.transfer_cip_f,
                     chw_data.ref_vct, chw_data.ref_ois, chw_data.ref_ctc, 
                     chw_data.ref_pmtct, chw_data.ref_fp, chw_data.ref_sg, 
                     chw_data.ref_tb, chw_data.conf_ref]
        all_data.append(this_list)
    table = Table(all_data, repeatRows=4, splitByRow=0)
    table.setStyle(TableStyle([('FONTSIZE', (0, 0), (-1, -1), 6),
                               ('SPAN', (5, 0), (12, 0)),
                               ('SPAN', (5, 1), (8, 1)),
                               ('SPAN', (5, 2), (6, 2)),
                               ('SPAN', (7, 2), (8, 2)),
                               ('SPAN', (9, 1), (12, 1)),
                               ('SPAN', (9, 2), (10, 2)),
                               ('SPAN', (11, 2), (12, 2)),
                               ('SPAN', (13, 1), (16, 1)),
                               ('SPAN', (13, 2), (14,2)),
                               ('SPAN', (15, 2), (16, 2)),
                               ('SPAN', (17, 1), (20, 1)),
                               ('SPAN', (17, 2), (18, 2)),
                               ('SPAN', (19, 2), (20, 2)),
                               ('SPAN', (21, 1), (24, 1)),
                               ('SPAN', (21, 2), (22, 2)),
                               ('SPAN', (23, 2), (24, 2)),
                               ('SPAN', (25, 1), (31, 1)),
                               ('INNERGRID', (0,0), (-1,-1), 0.25, colors.black),
                               ('BOX', (0,0), (-1,-1), 0.25, colors.black)]))
    elements.append(table)
    doc.build(elements)
    return response

def hbc_sum_pdf(request, month, year):
    ''' Creates PDF file of HBC monthly summary report'''
    case_name = "Pathfinder_1" 
    month = int(month)
    year = int(year)
    startdate = datetime(year, month, 01).date()
    nextmonth = month + 1
    if nextmonth == 13:
        nextmonth = 1
    enddate = datetime(year, nextmonth, 01).date()
    
    try:
        case = Case.objects.get(name=case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    data_by_chw = get_data_by_chw(case)
    chw_obj = HBCMonthlySummaryData(case, data_by_chw, startdate, enddate)
    
    response = HttpResponse(mimetype='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=hbc_monthly_summary_%s-%s.pdf'\
                                        % (month, year)
    doc = SimpleDocTemplate(response)
    elements = []
    
    table1 = []
    table1.append(['Number of providers - who reported this month:',
                chw_obj.providers_reporting, '- who did not report this month:', 
                chw_obj.providers_not_reporting])
    t1 = Table(table1)
    t1.setStyle(TableStyle([('FONTSIZE', (0, 0), (-1, -1), 8),
                            ('INNERGRID', (0,0), (-1,-1), 0.25, colors.black),
                            ('BOX', (0,0), (-1,-1), 0.25, colors.black)]))
    elements.append(t1)

    table2 = []
    table2.append(['', 'Total', '', 'Less than 15', '', '15 to 24', '', '25-49',
                 '', '50 and above', ''])
    table2.append(['', 'M', 'F', 'M', 'F', 'M', 'F', 'M', 'F', 'M', 'F'])
    table2.append(['1. Number of New Clients enrolled this month', 
                chw_obj.new_total_m, chw_obj.new_total_f, chw_obj.new_0_14_m,
                chw_obj.new_0_14_f, chw_obj.new_15_24_m, chw_obj.new_15_24_f,
                chw_obj.new_25_49_m, chw_obj.new_25_49_f, chw_obj.new_50_m,
                chw_obj.new_50_f])
    table2.append(['2. New and continuing clients receiving services this month',
                chw_obj.all_total_m, chw_obj.all_total_f, '', '', '', '', '',
                '', '', ''])
    table2.append(['HIV status', '', '', '', '', '', '', '', '', '', ''])
    table2.append(['Positive', chw_obj.positive_m, chw_obj.positive_f, '',
                     '', '', '', '', '', '', ''])
    table2.append(['Negative', chw_obj.negative_m, chw_obj.negative_f, '',
                    '', '', '', '', '', '', ''])
    table2.append(['Unknown', chw_obj.unknown_m, chw_obj.unknown_f, '', '',
                     '', '', '', '', '', ''])
    table2.append(['CTC enrollment status', '', '', '', '', '', '', '', '',
                     '', ''])
    table2.append(['Enrolled in CTC but not on ARVs', chw_obj.ctc_m, 
                     chw_obj.ctc_f, '', '', '', '', '', '', '', ''])
    table2.append(['Enrolled in CTC and on ARVs', chw_obj.ctc_arv_m,
                     chw_obj.ctc_arv_f, '', '', '', '', '', '', '', ''])
    table2.append(['Not enrolled in CTC', chw_obj.no_ctc_m, 
                     chw_obj.no_ctc_f, '', '', '', '', '', '', '', ''])
    table2.append(['3. Number of clients ever enrolled in HBC', 
                     chw_obj.enrolled_m, chw_obj.enrolled_f, '', '', '', '',
                      '', '', '', ''])
    t2 = Table(table2)
    t2.setStyle(TableStyle([('FONTSIZE', (0, 0), (-1, -1), 8),
                            ('SPAN', (1, 0), (2, 0)), #Total
                            ('SPAN', (3, 0), (4, 0)), #Less than 15
                            ('SPAN', (5, 0), (6, 0)), #15-24
                            ('SPAN', (7, 0), (8, 0)), #25-49
                            ('SPAN', (9, 0), (10, 0)), #50 and above
                            ('INNERGRID', (0,0), (-1,-1), 0.25, colors.black),
                            ('BOX', (0,0), (-1,-1), 0.25, colors.black)]))
    elements.append(t2)
    
    table3 = []
    table3.append(['', 'Died', 'Lost', 'Transferred to other HBC services', 
                'Migrated', 'No longer in need of services', 'Opted out', 
                'Total'])
    table3.append(['4. Number of clients no longer receiving services', 
                chw_obj.died, chw_obj.lost, chw_obj.transferred, 
                chw_obj.migrated, chw_obj.no_need, chw_obj.opt_out, 
                chw_obj.total_no_services])
    t3 = Table(table3)
    t3.setStyle(TableStyle([('FONTSIZE', (0, 0), (-1, -1), 8),
                            ('INNERGRID', (0,0), (-1,-1), 0.25, colors.black),
                            ('BOX', (0,0), (-1,-1), 0.25, colors.black)]))
    elements.append(t3)

    doc.build(elements)
    return response

def sum_prov_pdf(request, chw_id, month, year):
    '''Creates PDF file of summary by provider report'''
    case_name = "Pathfinder_1"
    month = int(month)
    year = int(year)
    startdate = datetime(year, month, 01).date()
    nextmonth = month + 1
    if nextmonth == 13:
        nextmonth = 1
    enddate = datetime(year, nextmonth, 01).date()
    
    try:
        case = Case.objects.get(name=case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    data_by_chw = get_data_by_chw(case)
    chw_data = data_by_chw[chw_id]
    client_data_list = []
    for client_id, client_data in chw_data.items():
        client_obj = ProviderSummaryData(case, client_id, client_data, 
                                         startdate, enddate)
        if client_obj.num_visits != 0:
            client_data_list.append(client_obj)
    response = HttpResponse(mimetype='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=provider_summary_%s-%s.pdf'\
                                        % (month, year)
    doc = SimpleDocTemplate(response)
    doc.pagesize = (841.88976377952747, 595.27559055118104) # portrait
    elements = []
    all_data = []
    all_data.append(['HBC Patient Code', 'Age', 'Sex', 'HBC Status', 
                'Number of visits during', 'HIV status', 'Functional status',
                'CTC status', 'CTC Number', 'Material items provided', 
                'Services provided', 'Referrals made', 'Referrals completed'])
    for chw_data in client_data_list:
        this_list = [chw_data.patient_code, chw_data.age, chw_data.sex,
                      chw_data.hbc_status, chw_data.num_visits, 
                      chw_data.hiv_status, chw_data.functional_status,
                      chw_data.ctc_status, chw_data.ctc_num, 
                      chw_data.items_provided, chw_data.services_provided,
                      chw_data.referrals_made, chw_data.referrals_completed]
        all_data.append(this_list)
    colwidths = [35, 15, 15, 30, 30, 30, 50, 30, 30, 40, 40, 45, 45]
    table = Table(all_data, repeatRows=1, splitByRow=1)
    table.setStyle(TableStyle([('FONTSIZE', (0, 0), (-1, -1), 7),
                               ('INNERGRID', (0,0), (-1,-1), 0.25, colors.black),
                               ('BOX', (0,0), (-1,-1), 0.25, colors.black)]))

    elements.append(table)
    doc.build(elements)
    return response