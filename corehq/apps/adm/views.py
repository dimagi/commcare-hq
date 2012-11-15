import inspect
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from corehq.apps.crud.views import _process_crud_admin_form
from corehq.apps.domain.decorators import require_superuser, domain_admin_required
from dimagi.utils.data.crud import CRUDFormRequestManager, CRUDActionError
from dimagi.utils.modules import to_function
from dimagi.utils.web import render_to_response

@domain_admin_required
def default_adm_report(request, domain, template="adm/base_template.html", **kwargs):
    from corehq.apps.adm.reports import ADMSectionView
    context = dict(
        domain=domain,
        project=domain,
        report=dict(
            title="Select a Report to View",
            show=True,
            slug=None,
            is_async=True,
            section_name=ADMSectionView.section_name,
        )
    )
    context["report"].update(show_subsection_navigation=True)
    return render_to_response(request, template, context)

@require_superuser
def default_adm_admin(request):
    from corehq.apps.adm.admin.reports import ADMReportAdminInterface
    return HttpResponseRedirect(ADMReportAdminInterface.get_url())

@require_superuser
def adm_item_form(request, **kwargs):
    template = "crud/forms/crud.add_item.html"
    form_type = kwargs.get('form_type')
    if form_type == 'ConfigurableADMColumnChoiceForm':
        template = "adm/forms/configurable_admin_adm_item.html"
    return _process_crud_admin_form(request,
        template=template, base_loc="corehq.apps.adm.admin.forms", **kwargs)
