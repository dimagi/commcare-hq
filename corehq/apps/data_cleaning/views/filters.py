from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy
from django.views.generic import TemplateView
from memoized import memoized

from corehq import toggles
from corehq.apps.data_cleaning.forms.filters import AddColumnFilterForm
from corehq.apps.data_cleaning.views.mixins import BulkEditSessionViewMixin
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action
from corehq.util.timezones.utils import get_timezone


@method_decorator([
    use_bootstrap5,
    toggles.DATA_CLEANING_CASES.required_decorator(),
], name='dispatch')
class BaseFilterFormView(LoginAndDomainMixin, DomainViewMixin, HqHtmxActionMixin, TemplateView):
    pass


class PinnedFilterFormView(BulkEditSessionViewMixin, BaseFilterFormView):
    urlname = "data_cleaning_pinned_filter_form"
    template_name = "data_cleaning/forms/pinned_filter_form.html"
    session_not_found_message = gettext_lazy("Cannot retrieve pinned filters, session was not found.")

    @property
    def timezone(self):
        return get_timezone(self.request, self.domain)

    @property
    @memoized
    def form_filters(self):
        return [
            f.get_report_filter_class()(
                self.session, self.request, self.domain, self.timezone, use_bootstrap5=True
            ) for f in self.session.pinned_filters.all()
        ]

    @hq_hx_action('post')
    def update_filters(self, request, *args, **kwargs):
        [f.update_stored_value() for f in self.form_filters]
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'container_id': 'pinned-filters',
            'form_filters': [
                f.render() for f in self.form_filters
            ],
        })
        return context


class ColumnFilterFormView(BulkEditSessionViewMixin, BaseFilterFormView):
    urlname = "data_cleaning_column_filter_form"
    template_name = "data_cleaning/forms/column_filter_form.html"
    session_not_found_message = gettext_lazy("Cannot retrieve column filters, session was not found.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'container_id': 'column-filters',
            'add_filter_form': kwargs.pop('filter_form', AddColumnFilterForm()),
        })
        return context

    @hq_hx_action('post')
    def add_column_filter(self, request, *args, **kwargs):
        filter_form = AddColumnFilterForm(request.POST)
        if filter_form.is_valid():
            filter_form = None
        return self.get(request, filter_form=filter_form, *args, **kwargs)
