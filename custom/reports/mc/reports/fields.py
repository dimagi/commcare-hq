from corehq.apps.reports.filters.fixtures import AsyncDrillableFilter
from django.utils.translation import ugettext_lazy


class DistrictField(AsyncDrillableFilter):
    label = ugettext_lazy("District")
    slug = "location"
    hierarchy = [{"type": "district", "display": "name"}]

class HealthFacilityField(AsyncDrillableFilter):
    label = ugettext_lazy("Health Facility")
    slug = "location"
    hierarchy = [
        {"type": "district", "display": "name"},
        {"type": "hf", "parent_ref": "district_id", "references": "id", "display": "name"},
    ]

