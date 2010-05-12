from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect

from rapidsms.webui.utils import render_to_response, UnicodeWriter

from transformers.csv import format_csv 
from models import Case, SqlReport
from xformmanager.models import FormDefModel
from hq.utils import paginate, get_dates_reports
from domain.decorators import login_and_domain_required

import util
from custom.all.shared import *
from custom.pathfinder import ProviderSummaryData, WardSummaryData, HBCMonthlySummaryData

from StringIO import StringIO
import calendar
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
def sum_chw(request):
    ''' View the chw summary for the given case'''
    case_id = None
    year = None
    month = None
    if request:
        for item in request.GET.items():
            if item[0] == 'case':
                case_id = int(item[1])
    if case_id == None:
        return '''Sorry, no case has been selected'''
    domain = request.user.selected_domain
    # to configure these numbers use 'startdate_active', 'startdate_late', 
    # and 'enddate' in the url
    active, late, enddate = get_dates_reports(request, 30, 90)
    try:
        case = Case.objects.get(id=case_id)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    
    data_by_chw = get_data_by_chw(case)
    all_data = {}
    all_data['domain'] = domain.id
    all_data['case_id'] = case_id
    all_data['enddate'] = str(enddate.month) + "/" + str(enddate.day) + "/" +\
         str(enddate.year)
    all_data['startdate_active'] = str(active.month) + "/" + str(active.day) +\
        "/" + str(active.year)
    all_data['data'] = get_active_open_by_chw(data_by_chw, active, enddate)
    return render_to_response(request, "custom/all/chw_summary.html", all_data)

@login_and_domain_required
def individual_chw(request, domain_id, case_id, chw_id, enddate, active):
    '''View the cases of a single chw'''
    context = {}
    enddate = datetime.strptime(enddate, '%m/%d/%Y').date()
    active = datetime.strptime(active, '%m/%d/%Y').date()
    context['chw_id'] = chw_id
    case = Case.objects.get(id=case_id)
    data_by_chw = get_data_by_chw(case)
    user_data = get_user_data(chw_id)
    hcbpid = chw_id
    if 'hcbpid' in user_data:
        hcbpid = user_data['hcbpid']
    context['hcbpid'] = hcbpid
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
    ward = ""
    if request:
        for item in request.POST.items():
            if item[0] == 'ward':
                ward = item[1]
    context = get_ward_summary_data(startdate, enddate, month, year, ward)
    return render_to_response(request, 
                              "custom/pathfinder/ward_summary_report.html", 
                              context)

def hbc_monthly_sum(request):
    ''' View the hbc monthly summary report'''
    (month, year, startdate, enddate) = get_mon_year(request)
    ward = ""
    if request:
        for item in request.POST.items():
            if item[0] == 'ward':
                ward = item[1]
    context = get_hbc_summary_data(startdate, enddate, month, year, ward)
    return render_to_response(request, 
                              "custom/pathfinder/hbc_summary_report.html", 
                              context)
    
def select_prov(request):
    '''Given a ward, select the provider and date for the report'''
    context = {}
    ward = ""
    if request:
        for item in request.POST.items():
            if item[0] == 'ward':
                ward = item[1]
    providers = {}
    puis = PhoneUserInfo.objects.all()
    if puis != None:
        for pui in puis:
            additional_data = pui.additional_data
            if additional_data != None and "ward" in additional_data:
                if ward == additional_data["ward"]:
                    providers[pui.username + pui.phone.device_id] = pui.username
    context["providers"] = providers

    year = datetime.now().date().year
    years = []
    for i in range(0, 5):
        years.append(year-i)
    context["years"] = years
    return render_to_response(request, 
                              "custom/pathfinder/select_provider.html", 
                              context)
    
def ward_sum_csv(request, month, year, ward):
    ''' Creates CSV file of ward summary report'''
    (startdate, enddate) = get_start_end(month, year)
    chw_data_list = get_ward_chw_data_list(startdate, enddate, ward)
    output = StringIO()
    w = UnicodeWriter(output)
    w.writerow(['Ward:', ward])
    w.writerow(['Month:', calendar.month_name[int(month)]])
    w.writerow(['Year:', year])
    w.writerow([''])
    headers = get_ward_summary_headings()
    for header in headers:
        w.writerow(header)
    for row in chw_data_list:
        w.writerow(row)
    output.seek(0)
    response = HttpResponse(output.read(), mimetype='application/ms-excel')
    response["content-disposition"] = 'attachment; filename="ward_summary_%s_%s-%s.csv"'\
                                        % ( ward, month, year)
    return response

def sum_prov_csv(request, chw_id, month, year):
    ''' Creates CSV file of summary by provider report'''
    case_name = "Pathfinder_1"
    (startdate, enddate) = get_start_end(month, year)
    try:
        case = Case.objects.get(name=case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    data_by_chw = get_data_by_chw(case)

    chw_data = {}
    if chw_id in data_by_chw:
        chw_data = data_by_chw[chw_id]
    client_data_list = []
    for client_id, client_data in chw_data.items():
        client_obj = ProviderSummaryData(case, client_id, client_data, 
                                         startdate, enddate)
        if client_obj.num_visits != 0:
            client_data_list.append(client_obj)
    data = get_user_data(chw_id)
    provider_data_list = get_provider_data_list(data, month, year)
    username = ''
    if 'prov_name' in data:
        username = data['prov_name']
    output = StringIO()
    w = UnicodeWriter(output)
    for row in provider_data_list:
        w.writerow(row)
    w.writerow([''])
    w.writerow(get_provider_summary_headers())
    for row in client_data_list:
        w.writerow(row)
    output.seek(0)
    response = HttpResponse(output.read(), mimetype='application/ms-excel')
    response["content-disposition"] = 'attachment; filename="provider_%s_summary_%s-%s.csv"'\
                                        % ( username, month, year)
    return response

def hbc_sum_csv(request, month, year, ward):
    '''Creates csv file of HBC monthly summary report'''
    case_name = "Pathfinder_1" 
    (startdate, enddate) = get_start_end(month, year)
    
    try:
        case = Case.objects.get(name=case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    data_by_chw = get_data_by_chw(case)

    chw_obj = HBCMonthlySummaryData(case, data_by_chw, startdate, enddate, ward)
    output = StringIO()
    w = UnicodeWriter(output)
    w.writerow(['Ward:', ward])
    w.writerow(['Month:', calendar.month_name[int(month)]])
    w.writerow(['Year:', year])
    w.writerow([''])
    w.writerow(['Number of providers - who reported this month:',
                chw_obj.providers_reporting])
    w.writerow(['- who did not report this month:', 
                chw_obj.providers_not_reporting])
    w.writerow('')
    display_data = get_hbc_monthly_display(chw_obj)
    for row in display_data:
        w.writerow(row)
    w.writerow('')
    display_data2 = get_hbc_monthly_display_second(chw_obj)
    for row in display_data2:
        w.writerow(row)
    output.seek(0)
    response = HttpResponse(output.read(), mimetype='application/ms-excel')
    response["content-disposition"] = 'attachment; filename="hbc_monthly_summary_%s_%s-%s.csv"'\
                                        % ( ward, month, year)
    return response

def ward_sum_pdf(request, month, year, ward):
    ''' Creates PDF file of ward summary report'''
    (startdate, enddate) = get_start_end(month, year)

    response = HttpResponse(mimetype='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=ward_summary_%s_%s-%s.pdf'\
                                        % (ward, month, year)
    doc = SimpleDocTemplate(response)
    get_ward_summary_pdf(startdate, enddate, month, year, ward, doc)
    return response

def hbc_sum_pdf(request, month, year, ward):
    ''' Creates PDF file of HBC monthly summary report'''
    (startdate, enddate) = get_start_end(month, year)
    all_data = get_hbc_summary_data(startdate, enddate, month, year, ward)
    chw_obj = all_data["all_data"]
    
    response = HttpResponse(mimetype='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=hbc_monthly_summary_%s_%s-%s.pdf'\
                                        % (ward, month, year)
    doc = SimpleDocTemplate(response)
    get_hbc_monthly_pdf(month, year, chw_obj, ward, doc)
    return response

def sum_prov_pdf(request, chw_id, month, year):
    '''Creates PDF file of summary by provider report'''
    case_name = "Pathfinder_1"
    (startdate, enddate) = get_start_end(month, year)
    client_data_list = get_provider_data_by_case(case_name, chw_id, startdate, enddate)
    data = get_user_data(chw_id)
    username = ''
    if 'prov_name' in data:
        username = data['prov_name']
            
    response = HttpResponse(mimetype='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=provider_%s_summary_%s-%s.pdf'\
                                     % (username, month, year)
    doc = SimpleDocTemplate(response)
    get_provider_summary_pdf(month, year, chw_id, client_data_list, doc)
    return response
