from django.utils.translation import ugettext as _
from corehq.apps.locations.models import Location


def validate_report_parameters(parameters, config):
    for parameter in parameters:
        if not parameter in config:
            raise KeyError(_("Parameter '%s' is missing" % parameter))


def _is_location_CCT(location):
    return location.metadata.get("CCT", "").lower() == "true"


# A workaround to the problem occurring if a user selects 'All' in the first location filter dropdown
def get_location_hierarchy_by_id(location_id, domain, CCT_only=False):
    if location_id is None or len(location_id) == 0:
        return [location.get_id for location in Location.by_domain(domain) if not CCT_only or _is_location_CCT(location)]
    else:
        user_location = Location.get(location_id)
        locations = [location.get_id for location in user_location.descendants if not CCT_only or _is_location_CCT(location)]
        if not CCT_only or _is_location_CCT(user_location):
            locations.insert(0, user_location.get_id)
        return locations
