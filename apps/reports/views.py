from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.core.paginator import Paginator, InvalidPage, EmptyPage

from rapidsms.webui.utils import render_to_response

from models import Case
from xformmanager.models import FormDefModel
from hq.models import ExtUser

import util

from StringIO import StringIO
from transformers.csv import UnicodeWriter

@login_required()
def reports(request, template_name="list.html"):
    # not sure where this view will live in the UI yet
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        template_name="hq/no_permission.html"
        return render_to_response(request, template_name, context)
    extuser = ExtUser.objects.all().get(id=request.user.id)
    context['domain'] = extuser.domain
    context['case_reports'] = Case.objects.filter(domain=extuser.domain)
    report_module = util.get_custom_report_module(extuser.domain)
    if report_module:
        custom = util.get_custom_reports(report_module)
        context['custom_reports'] = custom
    else: 
        # if no custom and no case reports, return a generic
        # error message
        if not context['case_reports']:
            return render_to_response(request, 
                                      "domain_not_found.html",
                                      context)
    return render_to_response(request, template_name, context)

@login_required()
def case_flat(request, case_id, template_name="case_flat.html"):
    '''A flat view of the topmost data for all cases'''
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        template_name="hq/no_permission.html"
        return render_to_response(request, template_name, context)
    extuser = ExtUser.objects.all().get(id=request.user.id)
    case = Case.objects.get(id=case_id)
    
    context['cols'] = case.get_column_names()
    
    data = case.get_topmost_data()
    keys = data.keys()
    keys.sort()
    flattened = []
    for key in keys:
        flattened.append(data[key])
    
    
    context['data'] = _paginate(request, flattened)    
    context['case'] = case
    
    return render_to_response(request, template_name, context)

@login_required()
def single_case_view(request, case_id, case_instance_id, template_name="single_case.html"):
    '''View for all of a single case's data, broken down by form.'''
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        template_name="hq/no_permission.html"
        return render_to_response(request, template_name, context)
    extuser = ExtUser.objects.all().get(id=request.user.id)
    
    case = Case.objects.get(id=case_id)
    data = case.get_data_for_case(case_instance_id)
    
    context['case_instance_id'] = case_instance_id
    context['case_data'] = data
    context['case'] = case
    
    return render_to_response(request, template_name, context)

@login_required()
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


@login_required()
def custom_report(request, domain_id, report_name):
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        return render_to_response(request, "hq/no_permission.html", 
                                  context)
    extuser = ExtUser.objects.all().get(id=request.user.id)
    context["domain"] = extuser.domain
    context["report_name"] = report_name
    report_module = util.get_custom_report_module(extuser.domain)
    if not report_module:
        return render_to_response(request, 
                                  "domain_not_found.html",
                                  context)
    if not hasattr(report_module, report_name):
        return render_to_response(request, 
                                  "custom/report_not_found.html",
                                  context)
    report_method = getattr(report_module, report_name)
    context["report_display"] = report_method.__doc__
    context["report_body"] = report_method(request)
    return render_to_response(request, "custom/base.html", context)

def _paginate(request, data):
    '''Helper call to provide pagination'''
    # todo? move this to a utils file somewhere.
    paginator = Paginator(data, 25) 
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
    try:
        data_pages = paginator.page(page)
    except (EmptyPage, InvalidPage):
        data_pages = paginator.page(paginator.num_pages)
    return data_pages
    