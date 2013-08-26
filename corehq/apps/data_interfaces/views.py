from corehq import CaseReassignmentInterface
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.reports.standard.export import ExcelExportReport
from corehq.apps.data_interfaces.dispatcher import DataInterfaceDispatcher, EditDataInterfaceDispatcher
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404

@login_and_domain_required
def default(request, domain):
    if not request.project or request.project.is_snapshot:
        raise Http404()
    if request.project.commtrack_enabled:
        if not request.couch_user.is_domain_admin():
            raise Http404()
        from corehq.apps.commtrack.views import ProductListView
        return HttpResponseRedirect(reverse(ProductListView.urlname,
                                            args=[domain]))
    if request.couch_user.can_view_reports():
        return HttpResponseRedirect(reverse(DataInterfaceDispatcher.name(),
                                            args=[domain, ExcelExportReport.slug]))
    exportable_reports = request.couch_user.get_exportable_reports(domain)
    if exportable_reports:
        return HttpResponseRedirect(reverse(DataInterfaceDispatcher.name(),
                                            args=[domain, exportable_reports[0]]))
    if request.couch_user.can_edit_data():
        return HttpResponseRedirect(reverse(EditDataInterfaceDispatcher.name(),
                                            args=[domain, CaseReassignmentInterface.slug]))
    raise Http404()
