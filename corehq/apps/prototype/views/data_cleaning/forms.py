from django.http import QueryDict
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from corehq import toggles
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.prototype.forms.data_cleaning import AddColumnFilterForm, CleanColumnDataForm
from corehq.apps.prototype.models.data_cleaning.cache_store import VisibleColumnStore, FakeCaseDataStore
from corehq.apps.prototype.models.data_cleaning.filters import ColumnFilter
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
            for c in FakeCaseTable.available_columns
            if c[0] not in visible_columns
        ]
        context.update({
            "columns": [
                {
                    'slug': c[0],
                    'config': c[1],
                }
                for c in FakeCaseTable.get_visible_columns(visible_columns)],
            "new_column_choices": new_column_choices,
            "table_selector": f"#{FakeCaseTable.css_id}",
            "container_id": FakeCaseTable.configure_columns_form_id,
        })
        return context

    def post(self, request, *args, **kwargs):
        VisibleColumnStore(request).set(request.POST.getlist('columns'))
        response = super().get(request, *args, **kwargs)
        return response

    def delete(self, request, *args, **kwargs):
        column_store = VisibleColumnStore(request)
        columns = column_store.get()
        columns.remove(request.GET['column'])
        column_store.set(columns)
        response = super().get(request, *args, **kwargs)
        return response

    def put(self, request, *args, **kwargs):
        column_store = VisibleColumnStore(request)
        columns = column_store.get()
        columns.append(QueryDict(request.body)['add_column'])
        column_store.set(columns)
        response = super().get(request, *args, **kwargs)
        return response


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.SAAS_PROTOTYPE.required_decorator(), name='dispatch')
class FilterColumnsFormView(TemplateView):
    urlname = "data_cleaning_filter_columns_form"
    template_name = "prototype/data_cleaning/partials/forms/filter_columns_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filter_form = kwargs.pop('filter_form') if 'filter_form' in kwargs else None
        context.update({
            "add_filter_form": filter_form or AddColumnFilterForm(FakeCaseTable),
            "column_filters": ColumnFilter.get_filters_from_cache(self.request),
            "table_selector": f"#{FakeCaseTable.css_id}",
            "container_id": FakeCaseTable.filter_form_id,
        })
        return context

    def delete(self, request, *args, **kwargs):
        index = int(request.GET['index'])
        ColumnFilter.delete_filter(request, index)
        response = super().get(request, *args, **kwargs)
        return response

    def put(self, request, *args, **kwargs):
        filter_form = AddColumnFilterForm(FakeCaseTable, QueryDict(request.body))
        if filter_form.is_valid():
            filter_form.add_filter(request)
            filter_form = None
        response = super().get(request, filter_form=filter_form, *args, **kwargs)
        return response


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.SAAS_PROTOTYPE.required_decorator(), name='dispatch')
class CleanDataFormView(TemplateView):
    urlname = "data_cleaning_clean_data_form"
    template_name = "prototype/data_cleaning/partials/forms/clean_data_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        clean_data_form = kwargs.pop('clean_data_form') if 'clean_data_form' in kwargs else None
        context.update({
            "clean_data_form": clean_data_form or CleanColumnDataForm(
                FakeCaseTable, FakeCaseDataStore(self.request)
            ),
            "table_selector": f"#{FakeCaseTable.css_id}",
            "container_id": FakeCaseTable.clean_data_form_id,
        })
        return context

    def post(self, request, *args, **kwargs):
        clean_data_form = CleanColumnDataForm(
            FakeCaseTable, FakeCaseDataStore(request), request.POST
        )
        if clean_data_form.is_valid():
            clean_data_form.apply_actions_to_data()
            clean_data_form = None
        response = super().get(request, clean_data_form=clean_data_form, *args, **kwargs)
        return response
