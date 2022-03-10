from custom.reports.mc.reports.models import AsyncDrillableFilter
from django.utils.translation import gettext_noop


class DistrictField(AsyncDrillableFilter):
    label = gettext_noop("District")
    slug = "location"
    hierarchy = [{"type": "district", "display": "name"}]


class HealthFacilityField(AsyncDrillableFilter):
    label = gettext_noop("Health Facility")
    slug = "location"
    hierarchy = [
        {"type": "district", "display": "name"},
        {"type": "hf", "parent_ref": "district_id", "references": "id", "display": "name"},
    ]
