from corehq.apps.locations.util import location_hierarchy_config
from custom.icds_reports.utils import icds_pre_release_features


def get_dashboard_template_context(domain, couch_user):
    context = {}
    context['location_hierarchy'] = location_hierarchy_config(domain)
    context['user_location_id'] = couch_user.get_location_id(domain)
    context['all_user_location_id'] = list(couch_user.get_sql_locations(
        domain
    ).location_ids())
    context['state_level_access'] = 'state' in set(
        [loc.location_type.code for loc in couch_user.get_sql_locations(
            domain
        )]
    )
    context['have_access_to_features'] = icds_pre_release_features(couch_user)
    context['have_access_to_all_locations'] = couch_user.has_permission(
        domain, 'access_all_locations'
    )

    if context['have_access_to_all_locations']:
        context['user_location_id'] = None

    if couch_user.is_web_user():
        context['is_web_user'] = True

    return context
