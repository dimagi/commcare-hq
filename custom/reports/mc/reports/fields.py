from custom.reports.mc.reports.models import AsyncDrillableFilter
from django.utils.translation import ugettext_noop


class DistrictField(AsyncDrillableFilter):
    label = ugettext_noop("District")
    slug = "location"
    hierarchy = [{"type": "district", "display": "name"}]


class HealthFacilityField(AsyncDrillableFilter):
    label = ugettext_noop("Health Facility")
    slug = "location"
    hierarchy = [
        {"type": "district", "display": "name"},
        {"type": "hf", "parent_ref": "district_id", "references": "id", "display": "name"},
    ]
