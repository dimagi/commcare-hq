from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy
from django.views.generic import TemplateView
from memoized import memoized

from corehq import toggles
from corehq.apps.data_cleaning.filters import (
    CaseOwnersPinnedFilter,
    CaseStatusPinnedFilter,
)
from corehq.apps.data_cleaning.models import PinnedFilterType
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
    session_not_found_message = gettext_lazy("Cannot retrieve pinned filter, session was not found.")

    @property
    def timezone(self):
        return get_timezone(self.request, self.domain)

    @staticmethod
    def get_form_filter_class(filter_type):
        return {
            PinnedFilterType.CASE_OWNERS: CaseOwnersPinnedFilter,
            PinnedFilterType.CASE_STATUS: CaseStatusPinnedFilter,
        }[filter_type]

    @property
    @memoized
    def form_filters(self):
        return [
            (f.filter_type, self.get_form_filter_class(f.filter_type)(
                self.request, self.domain, self.timezone, use_bootstrap5=True
            )) for f in self.session.pinned_filters.all()
        ]

    @hq_hx_action('post')
    def update_filters(self, request, *args, **kwargs):
        # todo
        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'container_id': 'pinned-filters',
            'form_filters': [
                f[1].render() for f in self.form_filters
            ],
        })
        return context
