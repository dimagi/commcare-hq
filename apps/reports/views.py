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
from custom.all.shared import get_data_by_chw, get_case_info, get_mon_year
from custom.pathfinder import ProviderSummaryData, WardSummaryData, HBCMonthlySummaryData

from StringIO import StringIO
from transformers.csv import UnicodeWriter
import calendar

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
    context = {}
    case_name = "Pathfinder_1"
    provider = None
    if request:
        for item in request.POST.items():
            if item[0] == 'provider':
                provider=item[1]
    (month, year, startdate, enddate) = get_mon_year(request)
    
    try:
        case = Case.objects.get(name=case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    data_by_chw = get_data_by_chw(case)
    chw_data = data_by_chw[provider]
    client_data_list = []
    for client_id, client_data in chw_data.items():
        client_obj = ProviderSummaryData(case, client_id, client_data, 
                                         startdate, enddate)
        if client_obj.num_visits != 0:
            client_data_list.append(client_obj)

    context["all_data"] = client_data_list
    context["region"] = None #TODO: get region
    context["district"] = None #TODO: get district
    context["ward"] = None #TODO: get ward
    context["month"] = calendar.month_name[month]
    context["year"] = year
    context["prov_name"] = None #TODO: get name
    context["num"] = provider
    context["sex"] = None #TODO: get sex
    context["trained"] = None #TODO: get trained
    context["org"] = None #TODO: get org
    context["days_train"] = None #TODO: get days_train
    context["category"] = None #TODO: get category
    context["supervisor"] = None #TODO: get supervisor
    context["facility"] = None #TODO: get facility
    context["supervisor_id"] = None #TODO: get supervisor_id
    context["org_support"] = None #TODO: get org_support

    return render_to_response(request, 
                              "custom/pathfinder/sum_by_provider_report.html",
                              context)

def sum_ward(request):
    '''View the ward summary report'''
    context = {}
    case_name = "Pathfinder_1" 
    (month, year, startdate, enddate) = get_mon_year(request)

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
    context["all_data"] = chw_data_list
    context["year"] = year
    context["month"] = calendar.month_name[month]
    return render_to_response(request, 
                              "custom/pathfinder/ward_summary_report.html", 
                              context)

def hbc_monthly_sum(request):
    ''' View the hbc monthly summary report'''
    context = {}
    case_name = "Pathfinder_1" 
    (month, year, startdate, enddate) = get_mon_year(request)
    
    try:
        case = Case.objects.get(name=case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    data_by_chw = get_data_by_chw(case)
    chw_obj = HBCMonthlySummaryData(case, data_by_chw, startdate, enddate)
    context["all_data"] = chw_obj
    context["month"] = calendar.month_name[month]
    context["year"] = year
    return render_to_response(request, 
                              "custom/pathfinder/hbc_summary_report.html", 
                              context)