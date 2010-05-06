from datetime import datetime
from django.template.loader import render_to_string
from apps.reports.models import Case

def chw_summary(request, domain=None):
    '''The chw_summary report'''
    if not domain:
        domain = request.user.selected_domain
    cases = Case.objects.filter(domain=domain)
    case_data = {}
    for case in cases:
        case_data[case.id] = case.name
    return render_to_string("custom/all/select_case.html", {"data": case_data})
