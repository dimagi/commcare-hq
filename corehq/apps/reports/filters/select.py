from django.utils.translation import ugettext_noop
from corehq.apps.domain.models import Domain, LICENSES
from corehq.apps.reports.filters.base import BaseSingleOptionFilter


class SelectRegionFilter(BaseSingleOptionFilter):
    slug = "region"
    label = ugettext_noop("Region")
    default_text = ugettext_noop("All Regions")

    @property
    def options(self):
        if hasattr(Domain, 'regions'):
            available_regions = [(d.replace(' ', '+'), d) for d in Domain.regions()]
        else:
            available_regions = []
        return available_regions


class SelectLicenseFilter(BaseSingleOptionFilter):
    slug = "license"
    label = ugettext_noop("License")
    default_text = ugettext_noop("All Licenses")

    @property
    def options(self):
        return [(code, license_name) for code, license_name in LICENSES.items()]


class SelectCategoryFilter(BaseSingleOptionFilter):
    slug = "category"
    label = ugettext_noop("Category")
    default_text = ugettext_noop("All Categories")

    @property
    def options(self):
        if hasattr(Domain, 'categories'):
            available_categories = [(d.replace(' ', '+'), d) for d in Domain.categories()]
        else:
            available_categories = []
        return available_categories
