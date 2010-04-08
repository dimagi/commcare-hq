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
from custom.all.shared import *
from custom.pathfinder import ProviderSummaryData, WardSummaryData, HBCMonthlySummaryData

from StringIO import StringIO
from transformers.csv import UnicodeWriter
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
    output = StringIO()
    w = UnicodeWriter(output)
    headers = get_ward_summary_headings()
    for header in headers:
        w.writerow(header)
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
    output = StringIO()
    w = UnicodeWriter(output)
    w.writerow(get_provider_summary_headers())
    for row in client_data_list:
        w.writerow(row)
    output.seek(0)
    response = HttpResponse(output.read(), mimetype='application/ms-excel')
    response["content-disposition"] = 'attachment; filename="provider_%s_summary_%s-%s.csv"'\
                                        % ( chw_id, month, year)
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
    response["content-disposition"] = 'attachment; filename="hbc_monthly_summary_%s-%s.csv"'\
                                        % ( month, year)
    return response

def ward_sum_pdf(request, month, year, ward):
    ''' Creates PDF file of ward summary report'''
    (startdate, enddate) = get_start_end(month, year)
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

    response = HttpResponse(mimetype='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=ward_summary_%s-%s.pdf'\
                                        % (month, year)
    doc = SimpleDocTemplate(response)
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
    return response

def hbc_sum_pdf(request, month, year, ward):
    ''' Creates PDF file of HBC monthly summary report'''
    case_name = "Pathfinder_1" 
    (startdate, enddate) = get_start_end(month, year)
    
    try:
        case = Case.objects.get(name=case_name)
    except Case.DoesNotExist:
        return '''Sorry, it doesn't look like the forms that this report 
                  depends on have been uploaded.'''
    data_by_chw = get_data_by_chw(case)
    chw_obj = HBCMonthlySummaryData(case, data_by_chw, startdate, enddate, ward)
    
    response = HttpResponse(mimetype='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=hbc_monthly_summary_%s-%s.pdf'\
                                        % (month, year)
    doc = SimpleDocTemplate(response)
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
    return response

def sum_prov_pdf(request, chw_id, month, year):
    '''Creates PDF file of summary by provider report'''
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
            
    response = HttpResponse(mimetype='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=provider_summary_%s-%s.pdf'\
                                     % (month, year)
    doc = SimpleDocTemplate(response)
    doc.pagesize = (841.88976377952747, 595.27559055118104) # landscape
    doc.title = "Home Based Care Patients Summary for Month"
    elements = []
    
    ps = ParagraphStyle(name='Normal', alignment=TA_CENTER) 
    para = Paragraph('Home Based Care Patients Summary for Month<br/>Month: %s<br/>Year: %s'% 
                     ( calendar.month_name[int(month)], year), ps)
    elements.append(para)
    
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
    return response