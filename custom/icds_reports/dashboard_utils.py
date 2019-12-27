from django.utils.translation import ugettext_lazy as _

from corehq.apps.hqwebapp.templatetags.hq_shared_tags import static
from corehq.apps.locations.util import location_hierarchy_config
from custom.icds_reports.const import NavigationSections
from custom.icds_reports.utils import icds_pre_release_features


def get_dashboard_template_context(domain, couch_user):
    context = {}
    context['location_hierarchy'] = location_hierarchy_config(domain)
    context['user_location_id'] = couch_user.get_location_id(domain)
    context['all_user_location_id'] = list(couch_user.get_sql_locations(
        domain
    ).location_ids())
    try:
        context['user_location_type'] = couch_user.get_sql_location(domain).location_type_name
    except AttributeError:
        context['user_location_type'] = ''
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

    context['nav_metadata'] = _get_nav_metadatada()
    return context


def _get_nav_metadatada():
    """
    Navigation metadata that is passed through to the Angular app.
    See program-summary.directive.js for an example of using this.
    """
    return {
        NavigationSections.MATERNAL_CHILD: {
            'label': _('Maternal and Child Nutrition'),
            'image': static('icds_reports/mobile/images/motherandchild.png')
        },
        NavigationSections.ICDS_CAS_REACH: {
            'label': _('ICDS-CAS Reach'),
            'image': static('icds_reports/mobile/images/statistics.png')
        },
        NavigationSections.DEMOGRAPHICS: {
            'label': _('Demographics'),
            'image': static('icds_reports/mobile/images/threegroup.png')
        },
        NavigationSections.AWC_INFRASTRUCTURE: {
            'label': _('AWC Infrastructure'),
            'image': static('icds_reports/mobile/images/bulb.png')
        },
    }
