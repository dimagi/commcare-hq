from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy
from django.views.generic import TemplateView
from memoized import memoized

from corehq.apps.data_cleaning.decorators import require_bulk_data_cleaning_cases
from corehq.apps.data_cleaning.forms.filters import AddFilterForm
from corehq.apps.data_cleaning.views.mixins import BulkEditSessionViewMixin
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action
from corehq.util.timezones.utils import get_timezone


@method_decorator([
    use_bootstrap5,
    require_bulk_data_cleaning_cases,
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

    @hq_hx_action('post')
    def reset_filters(self, request, *args, **kwargs):
        self.session.reset_pinned_filters()
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'container_id': 'pinned-filters',
            'form_filters': [
                f.render() for f in self.form_filters
            ],
            'has_values': self.session.has_pinned_values,
        })
        return context


class ManageFiltersFormView(BulkEditSessionViewMixin, BaseFilterFormView):
    urlname = "data_cleaning_manage_filters"
    template_name = "data_cleaning/forms/manage_filters_form.html"
    session_not_found_message = gettext_lazy("Cannot retrieve filters, session was not found.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'container_id': 'manage-filters',
            'active_filters': self.session.filters.all(),
            'add_filter_form': kwargs.pop('filter_form', None) or AddFilterForm(self.session),
        })
        return context

    @hq_hx_action('post')
    def add_filter(self, request, *args, **kwargs):
        filter_form = AddFilterForm(self.session, request.POST)
        if filter_form.is_valid():
            filter_form.create_filter()
            filter_form = None
        return self.get(request, filter_form=filter_form, *args, **kwargs)

    @hq_hx_action('post')
    def update_filter_order(self, request, *args, **kwargs):
        filter_ids = request.POST.getlist('filter_ids')
        self.session.update_filter_order(filter_ids)
        return self.get(request, *args, **kwargs)

    @hq_hx_action('post')
    def delete_filter(self, request, *args, **kwargs):
        self.session.remove_filter(request.POST['delete_id'])
        return self.get(request, *args, **kwargs)
