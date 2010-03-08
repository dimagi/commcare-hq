from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect

from rapidsms.webui.utils import render_to_response

from transformers.csv import format_csv 
from reports.models import Case, SqlReport
from xformmanager.models import FormDefModel
from hq.utils import paginate
from domain.decorators import login_and_domain_required

import reports.util as util
from reports.custom.all.shared import get_data_by_chw, get_case_info

from StringIO import StringIO
from transformers.csv import UnicodeWriter


@login_and_domain_required    
def all_mothers_report(request):
    '''View all mothers - default'''
    return custom_report(request, 3, "chw_submission_details", "all")

@login_and_domain_required
def hi_risk_report(request):
    '''View only hi risk'''
    return custom_report(request, 3, "hi_risk_pregnancies", "risk")

@login_and_domain_required
def mother_details(request):
    '''view details for a mother'''
    return custom_report(request, 3, "_mother_summary", "single")
    


def custom_report(request, domain_id, report_name, page):
    context = {}
    context['page'] = page
    context["report_name"] = report_name
    report_method = util.get_report_method(request.user.selected_domain, report_name)
    # return HttpResponse(report_method(request))
    if not report_method:
        return render_to_response(request, 
                                  "report_not_found.html",
                                  context)
    context["report_display"] = report_method.__doc__
    context["report_body"] = report_method(request)
    
    if 'search' not in request.GET.keys(): 
        context['search_term'] = ''
    else:
        context['search_term'] = request.GET['search']

    return render_to_response(request, "report_base.html", context)