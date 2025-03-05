from django.http import Http404
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy, gettext as _
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
from corehq.util.htmx_action import HqHtmxActionMixin
from corehq.util.timezones.utils import get_timezone


@method_decorator([
    use_bootstrap5,
    toggles.DATA_CLEANING_CASES.required_decorator(),
], name='dispatch')
class BaseFilterFormView(HqHtmxActionMixin, LoginAndDomainMixin, DomainViewMixin, TemplateView):
    pass


class PinnedFilterFormView(BulkEditSessionViewMixin, BaseFilterFormView):
    urlname = "data_cleaning_pinned_filter_form"
    template_name = "data_cleaning/forms/pinned_filter_form.html"
    session_not_found_message = gettext_lazy("Cannot retrieve pinned filter, session was not found.")

    @property
    @memoized
    def timezone(self):
        return get_timezone(self.request, self.domain)

    @property
    def filter_type(self):
        return self.kwargs['filter_type']

    @property
    def form_filter_class(self):
        filter_type_to_class = {
            PinnedFilterType.CASE_OWNERS: CaseOwnersPinnedFilter,
            PinnedFilterType.CASE_STATUS: CaseStatusPinnedFilter,
        }
        try:
            return filter_type_to_class[self.filter_type]
        except KeyError:
            raise Http404(_("unsupported filter type: {}").format(self.filter_type))

    @property
    @memoized
    def form_filter(self):
        return self.form_filter_class(
            self.request, self.domain, self.timezone, use_bootstrap5=True
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "filter_type": self.filter_type,
            "rendered_filter": self.form_filter.render(),
        })
        return context
