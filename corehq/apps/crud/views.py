import inspect
from django.http import HttpResponseBadRequest, HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic.base import TemplateView
from corehq.apps.domain.decorators import require_superuser
from dimagi.utils.data.crud import CRUDFormRequestManager, CRUDActionError
from dimagi.utils.modules import to_function

class BaseAdminCRUDFormView(TemplateView):
    template_name = "crud/forms/crud.add_item.html"
    base_loc = None

    def is_form_class_valid(self, form_class):
        return True

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        form_type = kwargs.get('form_type')
        action = kwargs.get('action', 'new')
        item_id = kwargs.get("item_id")

        try:
            form_class = to_function("%s.%s" % (self.base_loc, form_type))
        except Exception:
            form_class = None

        if not inspect.isclass(form_class):
            return HttpResponseBadRequest("'%s' should be a class name in %s" % (form_type, self.base_loc))

        if self.is_form_class_valid(form_class):
            try:
                form_manager = CRUDFormRequestManager(request, form_class, self.template_name,
                    doc_id=item_id, delete=bool(action == 'delete'))
                return HttpResponse(form_manager.json_response)
            except CRUDActionError as e:
                return HttpResponseBadRequest(e)
        else:
            return HttpResponseBadRequest("Not a valid form class.")
