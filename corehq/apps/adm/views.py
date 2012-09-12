import json
from django.http import HttpResponse, HttpResponseBadRequest
import inspect
from django.template.loader import render_to_string
from corehq.apps.domain.decorators import require_superuser, require_previewer
from dimagi.utils.data.editable_items import InterfaceEditableItemForm
from dimagi.utils.modules import to_function

@require_previewer
def default_adm_report(request, domain, template="reports/base_template.html, **kwargs):
    context = dict(
        domain=domain,
        report=dict(
            title="Select a Report to View",
            show=request.couch_user.can_view_reports() or request.couch_user.get_viewable_reports(),
            slug=None,
            is_async=True,
            section_name="Project Reports",
        )
    )
    context["report"].update(show_subsection_navigation=adm_utils.show_adm_nav(domain, context))
    return render_to_response(request, template, context)


@require_superuser
def adm_item_form(request, template="adm/forms/admin_adm_item.html", **kwargs):
    form_type = kwargs.get('form_type')
    action = kwargs.get('action', 'new')
    item_id = kwargs.get("item_id")

    try:
        form_class = to_function("corehq.apps.adm.forms.%s" % form_type)
    except Exception:
        form_class = None

    if not inspect.isclass(form_class):
        return HttpResponseBadRequest("'%s' should be a class name in corehq.apps.adm.forms" % form_type)
    if not issubclass(form_class, InterfaceEditableItemForm):
        return HttpResponseBadRequest("'%s' should be a subclass of InterfaceEditableItemForm" % form_type)

    from corehq.apps.adm.forms import ConfigurableADMColumnForm
    if form_class == ConfigurableADMColumnForm:
        template = "adm/forms/configurable_admin_adm_item.html"

    print "FORM CLASS", form_class
    print "POST", request.POST

    success = False
    delete_item = bool(action == 'delete')
    form = None
    adm_item = None
    errors = []
    item_result = []

    if action == 'update' or delete_item:
        if not item_id:
            return HttpResponseBadRequest("an item_id is required in order to update")
        try:
            adm_item = form_class._item_class.get(item_id)
        except Exception as e:
            return HttpResponseBadRequest("There was an issue retrieving the item with doc_id %s. Error: %s" %
                (item_id, e)
            )
        if delete_item:
            try:
                success = True
                adm_item.delete()
            except Exception as e:
                errors.append("Could not delete item %s due to error: %s" % (item_id, e))

    if request.method == 'POST' and not delete_item:
        form = form_class(request.POST, item_id=item_id)
        if form.is_valid():
            success = True
            item_result = form.update(adm_item) if adm_item else form.save()
            print item_result

    if request.method == 'GET' or success:
        if adm_item and not delete_item:
            form = form_class(adm_item._doc, item_id=item_id)
        else:
            form = form_class()

    context = dict(form=form)
    return HttpResponse(json.dumps(dict(
        success=success,
        deleted=delete_item,
        form_update=render_to_string(template, context) if form else "",
        rows=item_result,
        errors=errors
    )))
