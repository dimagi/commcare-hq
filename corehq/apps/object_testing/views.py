from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from memoized import memoized

from corehq import toggles
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.object_testing.forms import (
    ObjectTestCreateForm,
    ObjectTestUpdateForm,
)
from corehq.apps.object_testing.framework.exceptions import ObjectTestAssertionError
from corehq.apps.object_testing.framework.main import execute_object_test
from corehq.apps.object_testing.models import ObjectTest
from corehq.apps.settings.views import BaseProjectDataView
from corehq.util import reverse


@method_decorator(toggles.UCR_EXPRESSION_REGISTRY.required_decorator(), name='dispatch')
class ObjectTestListView(BaseProjectDataView, CRUDPaginatedViewMixin):
    page_title = gettext_lazy("Object Testing")
    urlname = "object_test:list"
    template_name = "object_testing/object_test_list.html"
    create_item_form_class = "form form-horizontal"

    @property
    def base_query(self):
        return ObjectTest.objects.filter(domain=self.domain)

    @property
    def total(self):
        return self.base_query.count()

    def post(self, *args, **kwargs):
        return self.paginate_crud_response

    @property
    def column_names(self):
        return [
            _("Name"),
            _("Description"),
            # _("URL"),
            _("Actions"),
        ]

    @property
    def page_context(self):
        return self.pagination_context

    @property
    def paginated_list(self):
        for api in self.base_query.all():
            yield {
                "itemData": self._item_data(api),
                "template": "base-object-test-template",
            }

    def _item_data(self, obj):
        return {
            'id': obj.id,
            'name': obj.name,
            'description': obj.description,
            "edit_url": reverse("object_test:edit", args=[self.domain, obj.id])
        }

    def get_create_form(self, is_blank=False):
        if self.request.method == 'POST' and not is_blank:
            return ObjectTestCreateForm(self.request, self.request.POST)
        return ObjectTestCreateForm(self.request)

    def get_create_item_data(self, create_form):
        new_test = create_form.save()
        return {
            "itemData": self._item_data(new_test),
            "template": "base-object-test-template",
        }

    def get_deleted_item_data(self, item_id):
        test_obj = ObjectTest.objects.get(id=item_id)
        test_obj.delete()
        return {
            'itemData': self._item_data(test_obj),
            'template': 'delete-object-test-template',
        }


@method_decorator(toggles.UCR_EXPRESSION_REGISTRY.required_decorator(), name='dispatch')
class ObjectTestEditView(BaseProjectDataView):
    page_title = gettext_lazy("Test")
    urlname = "object_test:edit"
    template_name = "object_testing/object_test_edit.html"

    @property
    def test_id(self):
        return self.kwargs['id']

    @property
    @memoized
    def object_test(self):
        try:
            return ObjectTest.objects.get(id=self.test_id)
        except ObjectTest.DoesNotExist:
            raise Http404

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain, self.test_id,))

    def get_form(self):
        if self.request.method == 'POST':
            return ObjectTestUpdateForm(self.request, self.object_test, self.request.POST)
        return ObjectTestUpdateForm(self.request, self.object_test)

    @property
    def main_context(self):
        main_context = super().main_context

        main_context.update({
            "form": self.get_form(),
            "object_test": self.object_test,
            "page_title": self.page_title
        })
        return main_context

    def post(self, request, domain, **kwargs):
        if "execute" in self.request.POST:
            try:
                execute_object_test(self.object_test)
            except ObjectTestAssertionError as e:
                messages.error(request, str(e))
            else:
                messages.info(request, "Success")
            return redirect(self.urlname, self.domain, self.test_id)
        else:
            form = self.get_form()
            if form.is_valid():
                form.save()
                messages.success(request, _("Test updated successfully."))
                return redirect(self.urlname, self.domain, self.test_id)
            return self.get(request, self.domain, **kwargs)
