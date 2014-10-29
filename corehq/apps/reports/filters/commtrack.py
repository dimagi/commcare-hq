from corehq.apps.reports.filters.base import CheckboxFilter

from django.utils.translation import ugettext_lazy


class ArchivedProducts(CheckboxFilter):
    label = ugettext_lazy("Include archived products?")
    slug = "archived_products"
