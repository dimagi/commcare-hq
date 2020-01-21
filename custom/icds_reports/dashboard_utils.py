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
    context['nav_menu_items'] = _get_nav_menu_items()
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


def _get_nav_menu_items():
    return {
        'Maternal and Child Nutrition': [
            {
                'name': 'Prevalence of Underweight (Weight-for-Age)',
                'route': 'maternal_and_child/underweight_children',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'Prevalence of Wasting (Weight-for-Height)',
                'route': 'maternal_and_child/wasting',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'Prevalence of Stunting (Height-for-Age)',
                'route': 'maternal_and_child/stunting',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'Newborns with Low Birth Weight',
                'route': 'maternal_and_child/low_birth',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'Early Initiation of Breastfeeding',
                'route': 'maternal_and_child/early_initiation',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'Exclusive Breastfeeding',
                'route': 'maternal_and_child/exclusive_breastfeeding',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'Children initiated appropriate complementary feeding',
                'route': 'maternal_and_child/children_initiated',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'Institutional deliveries',
                'route': 'maternal_and_child/institutional_deliveries',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'Immunization coverage (at age 1 year)',
                'route': 'maternal_and_child/immunization_coverage',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
        ],
        'ICDS-CAS Reach': [
            {
                'name': 'AWCs Daily Status',
                'route': 'icds_cas_reach/awc_daily_status',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'AWCs Launched',
                'route': 'icds_cas_reach/awcs_covered',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            }
        ],
        'Demographics': [
            {
                'name': 'Registered Households',
                'route': 'demographics/registered_household',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'Aadhaar-seeded Beneficiaries',
                'route': 'demographics/adhaar',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'Children enrolled for Anganwadi Services',
                'route': 'demographics/enrolled_children',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'Pregnant Women enrolled for Anganwadi Services',
                'route': 'demographics/enrolled_women',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'Lactating Mothers enrolled for Anganwadi Services',
                'route': 'demographics/lactating_enrolled_women',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'Out of school Adolescent girls(11-14 years)',
                'route': 'demographics/adolescent_girls',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            }
        ],
        'AWC Infrastructure': [
            {
                'name': 'AWCs Reported Clean Drinking Water',
                'route': 'awc_infrastructure/clean_water',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'AWCs Reported functional toilet',
                'route': 'awc_infrastructure/functional_toilet',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'AWCs Reported Weighing Scale: Infants',
                'route': 'awc_infrastructure/infants_weight_scale',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'AWCs Reported Weighing Scale: Mother and Child',
                'route': 'awc_infrastructure/adult_weight_scale',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'AWCs Reported Medicine kit',
                'route': 'awc_infrastructure/medicine_kit',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'AWCs Reported Infantometer',
                'route': 'awc_infrastructure/infantometer',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            },
            {
                'name': 'AWCs Reported Stadiometer',
                'route': 'awc_infrastructure/stadiometer',
                'children': False,
                'featureFlagOnly': False,
                'showInMobile': True,
                'showInWeb': True
            }
        ],
    }
