import inspect
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from corehq.apps.domain.decorators import require_superuser, require_previewer, login_and_domain_required
from dimagi.utils.data.crud import CRUDFormRequestManager, CRUDActionError
from dimagi.utils.modules import to_function
from dimagi.utils.web import render_to_response

@require_previewer
@login_and_domain_required
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
    from corehq.apps.adm.admin.reports import ADMReportEditInterface
    return HttpResponseRedirect(ADMReportEditInterface.get_url())

@require_superuser
def adm_item_form(request, template="adm/forms/admin_adm_item.html", **kwargs):
    form_type = kwargs.get('form_type')
    action = kwargs.get('action', 'new')
    item_id = kwargs.get("item_id")

    try:
        form_class = to_function("corehq.apps.adm.admin.forms.%s" % form_type)
    except Exception:
        form_class = None

    if not inspect.isclass(form_class):
        return HttpResponseBadRequest("'%s' should be a class name in corehq.apps.adm.admin.forms" % form_type)

    from corehq.apps.adm.admin.forms import ConfigurableADMColumnChoiceForm
    if form_class == ConfigurableADMColumnChoiceForm:
        template = "adm/forms/configurable_admin_adm_item.html"

    try:
        form_manager = CRUDFormRequestManager(request, form_class, template,
            doc_id=item_id, delete=bool(action == 'delete'))
        return HttpResponse(form_manager.json_response)
    except CRUDActionError as e:
        return HttpResponseBadRequest(e)
