from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy
from django.views.generic import TemplateView

from corehq import toggles
from corehq.apps.data_cleaning.views.mixins import BulkEditSessionViewMixin
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.util.htmx_action import HqHtmxActionMixin


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
    def filter_type(self):
        return self.kwargs['filter_type']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "filter_type": self.filter_type,
        })
        return context
