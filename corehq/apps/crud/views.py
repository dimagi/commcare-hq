import inspect
from django.http import HttpResponseBadRequest, HttpResponse
from dimagi.utils.data.crud import CRUDFormRequestManager, CRUDActionError
from dimagi.utils.modules import to_function

def _process_crud_admin_form(request, template="crud/forms/crud.add_item.html",
                   base_loc=None, **kwargs):
    form_type = kwargs.get('form_type')
    action = kwargs.get('action', 'new')
    item_id = kwargs.get("item_id")

    try:
        form_class = to_function("%s.%s" % (base_loc, form_type))
    except Exception:
        form_class = None

    if not inspect.isclass(form_class):
        return HttpResponseBadRequest("'%s' should be a class name in %s" % (form_type, base_loc))

    try:
        form_manager = CRUDFormRequestManager(request, form_class, template,
            doc_id=item_id, delete=bool(action == 'delete'))
        return HttpResponse(form_manager.json_response)
    except CRUDActionError as e:
        return HttpResponseBadRequest(e)