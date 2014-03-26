from django.utils.translation import ugettext as _
from corehq.apps.locations.models import Location


def validate_report_parameters(parameters, config):
    for parameter in parameters:
        if not parameter in config:
            raise KeyError(_("Parameter '%s' is missing" % parameter))


def get_location_hierarchy_by_id(location_id, domain):
    if location_id is None or len(location_id) == 0:
        # A workaround to the problem occurring if a user selects 'All' in the first location filter dropdown
        return [location.get_id for location in Location.by_domain(domain)]
    else:
        user_location = Location.get(location_id)
        return [location_id] + [descendant.get_id for descendant in user_location.descendants]
