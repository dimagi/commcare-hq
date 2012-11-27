from django.views.decorators.http import require_GET
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.reports.views import require_case_view_permission
from corehq.apps.reports import util
from corehq.apps.reports.standard import inspect
from dimagi.utils.web import   render_to_response
from django.http import HttpResponseRedirect
from django.contrib import messages
from casexml.apps.case.models import CommCareCase
from couchdbkit.exceptions import ResourceNotFound
#from fields import FilterUsersField
#from util import get_all_users_by_domain

@require_case_view_permission
@login_and_domain_required
@require_GET
def pact_case_details(request, domain, case_id):
    timezone = util.get_timezone(request.couch_user.user_id, domain)

    try:
        case = CommCareCase.get(case_id)
    except ResourceNotFound:
        case = None

    if case == None or case.doc_type != "CommCareCase" or case.domain != domain:
        messages.info(request, "Sorry, we couldn't find that case. If you think this is a mistake plase report an issue.")
        return HttpResponseRedirect(inspect.CaseListReport.get_url(domain))

    report_name = 'Details for Case "%s"' % case.name
#    form_lookups = dict((form.get_id, "%s: %s" % (form.received_on.date(), xmlns_to_name(domain, form.xmlns, get_app_id(form)))) for form in case.get_forms())
    return render_to_response(request, "reports/reportdata/case_details.html", {
        "domain": domain,
        "case_id": case_id,
#        "form_lookups": form_lookups,
        "slug":inspect.CaseListReport.slug,
        "report": dict(
            name=report_name,
            slug=inspect.CaseListReport.slug,
            is_async=False,
            ),
        "layout_flush_content": True,
        "timezone": timezone
    })
