from django.urls import reverse
from django.utils.decorators import method_decorator

from corehq import toggles
from corehq.apps.hqwebapp.decorators import (
    use_bootstrap5,
    use_alpinejs,
    use_htmx,
)
from corehq.apps.hqwebapp.views import BasePageView


@method_decorator(use_htmx, name='dispatch')
@method_decorator(use_alpinejs, name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.SAAS_PROTOTYPE.required_decorator(), name='dispatch')
class DataCleaningPrototypeView(BasePageView):
    urlname = "prototype_data_cleaning_case"
    template_name = 'prototype/data_cleaning/case_prototype.html'

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def page_context(self):
        return {
            "case_type": "child",
        }
