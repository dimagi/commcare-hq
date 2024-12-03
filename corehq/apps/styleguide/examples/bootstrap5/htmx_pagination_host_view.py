from django.utils.decorators import method_decorator
from django.urls import reverse

from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.views import BasePageView


@method_decorator(use_bootstrap5, name='dispatch')
class HtmxPaginationView(BasePageView):
    """
    This view hosts the Django Tables `ExamplePaginatedTableView`.
    """
    urlname = "styleguide_b5_htmx_pagination_view"
    template_name = "styleguide/bootstrap5/examples/htmx_pagination.html"

    @property
    def page_url(self):
        return reverse(self.urlname)
