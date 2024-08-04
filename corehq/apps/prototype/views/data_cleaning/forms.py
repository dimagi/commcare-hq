from django.http import QueryDict
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from memoized import memoized

from corehq import toggles
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.prototype.forms.data_cleaning import AddColumnFilterForm, CleanColumnDataForm
from corehq.apps.prototype.models.data_cleaning.cache_store import VisibleColumnStore, FakeCaseDataStore
from corehq.apps.prototype.models.data_cleaning.columns import CaseDataCleaningColumnManager
from corehq.apps.prototype.models.data_cleaning.tables import FakeCaseTable


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.SAAS_PROTOTYPE.required_decorator(), name='dispatch')
class ConfigureColumnsFormView(TemplateView):
    """A form view without using Django forms and crispy Forms,
    for comparison with the other form views."""
    urlname = "data_cleaning_configure_columns_form"
    template_name = "prototype/data_cleaning/partials/forms/configure_columns_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        visible_columns = VisibleColumnStore(self.request).get()
        new_column_choices = [
            (c[0], c[1].verbose_name)
            for c in CaseDataCleaningColumnManager.get_available_columns()
            if c[0] not in visible_columns
        ]
        context.update({
            "columns": [
                {
                    'slug': c[0],
                    'config': c[1],
                }
                for c in CaseDataCleaningColumnManager.get_visible_columns(visible_columns)],
            "new_column_choices": new_column_choices,
            "table_selector": f"#{FakeCaseTable.container_id}",
            "table_loading_id": FakeCaseTable.loading_indicator_id,
            "container_id": CaseDataCleaningColumnManager.configure_columns_form_id,
        })
        return context

    def post(self, request, *args, **kwargs):
        VisibleColumnStore(request).set(request.POST.getlist('columns'))
        return super().get(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        column_store = VisibleColumnStore(request)
        columns = column_store.get()
        columns.remove(request.GET['column'])
        column_store.set(columns)
        return super().get(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        column_store = VisibleColumnStore(request)
        columns = column_store.get()
        columns.append(QueryDict(request.body)['add_column'])
        column_store.set(columns)
        return super().get(request, *args, **kwargs)


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.SAAS_PROTOTYPE.required_decorator(), name='dispatch')
class FilterColumnsFormView(TemplateView):
    urlname = "data_cleaning_filter_columns_form"
    template_name = "prototype/data_cleaning/partials/forms/filter_columns_form.html"

    @property
    @memoized
    def column_manager(self):
        return CaseDataCleaningColumnManager(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filter_form = kwargs.pop('filter_form') if 'filter_form' in kwargs else None
        context.update({
            "add_filter_form": filter_form or AddColumnFilterForm(self.column_manager),
            "column_filters": self.column_manager.get_filters(),
            "table_selector": f"#{FakeCaseTable.container_id}",
            "table_loading_id": FakeCaseTable.loading_indicator_id,
            "container_id": self.column_manager.filter_form_id,
        })
        return context

    def post(self, request, *args, **kwargs):
        filter_slugs = request.POST.getlist('column_filters')
        self.column_manager.reorder_filters(filter_slugs)
        return super().get(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        index = int(request.GET['index'])
        self.column_manager.delete_filter(index)
        return super().get(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        filter_form = AddColumnFilterForm(self.column_manager, QueryDict(request.body))
        if filter_form.is_valid():
            filter_form.add_filter()
            filter_form = None
        return super().get(request, filter_form=filter_form, *args, **kwargs)


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.SAAS_PROTOTYPE.required_decorator(), name='dispatch')
class CleanDataFormView(TemplateView):
    urlname = "data_cleaning_clean_data_form"
    template_name = "prototype/data_cleaning/partials/forms/clean_data_form.html"

    @property
    def column_manager(self):
        return CaseDataCleaningColumnManager(self.request)

    @property
    def case_data_store(self):
        return FakeCaseDataStore(self.request)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        clean_data_form = kwargs.pop('clean_data_form', None)
        sticky_property = kwargs.pop('sticky_property', None)
        num_changes = kwargs.pop('num_changes', None)
        context.update({
            "clean_data_form": clean_data_form or CleanColumnDataForm(
                self.column_manager, self.case_data_store, initial={
                    'slug': sticky_property,
                }
            ),
            "num_changes": num_changes,
            "table_selector": f"#{FakeCaseTable.container_id}",
            "table_loading_id": FakeCaseTable.loading_indicator_id,
            "container_id": self.column_manager.clean_data_form_id,
        })
        return context

    def post(self, request, *args, **kwargs):
        clean_data_form = CleanColumnDataForm(
            self.column_manager, self.case_data_store, request.POST
        )
        num_changes = None
        sticky_property = None
        if clean_data_form.is_valid():
            num_changes = clean_data_form.apply_actions_to_data()
            sticky_property = clean_data_form.cleaned_data["slug"]
            clean_data_form = None
        return super().get(request,
                           clean_data_form=clean_data_form,
                           sticky_property=sticky_property,
                           num_changes=num_changes,
                           *args, **kwargs)
