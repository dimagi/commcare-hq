from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from corehq.apps.hqwebapp.templatetags.hq_shared_tags import static
from corehq.apps.locations.util import location_hierarchy_config
from corehq.toggles import ICDS_DASHBOARD_SHOW_MOBILE_APK, NAMESPACE_USER
from custom.icds_reports.const import NavigationSections
from custom.icds_reports.const import SDDSections
from custom.icds_reports.utils import (icds_pre_release_features,
                                       get_latest_issue_tracker_build_id)
from corehq.apps.cloudcare.utils import webapps_module
from corehq.apps.users.models import UserRole


from . import const

import attr


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
    context['show_mobile_apk'] = ICDS_DASHBOARD_SHOW_MOBILE_APK.enabled(couch_user.username,
                                                                        namespace=NAMESPACE_USER)
    context['have_access_to_all_locations'] = couch_user.has_permission(
        domain, 'access_all_locations'
    )

    if context['have_access_to_all_locations']:
        context['user_location_id'] = None

    if couch_user.is_web_user():
        context['is_web_user'] = True

    context['nav_metadata'] = _get_nav_metadatada()
    context['sdd_metadata'] = _get_sdd_metadata()
    context['nav_menu_items'] = _get_nav_menu_items()
    context['fact_sheet_sections'] = _get_factsheet_sections()
    context['MAPBOX_ACCESS_TOKEN'] = settings.MAPBOX_ACCESS_TOKEN
    context['support_email'] = settings.SUPPORT_EMAIL

    if couch_user.is_commcare_user() and _has_helpdesk_role(domain, couch_user):
        build_id = get_latest_issue_tracker_build_id()
        context['report_an_issue_url'] = webapps_module(
            domain=domain,
            app_id=build_id,
            module_id=0,
        )

    return context


def _has_helpdesk_role(domain, couch_user):
    user_roles = UserRole.by_domain(domain)
    helpdesk_roles_id = [
        role.get_id
        for role in user_roles
        if role.name in const.HELPDESK_ROLES
    ]
    domain_membership = couch_user.get_domain_membership(domain)
    return domain_membership.role_id in helpdesk_roles_id


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


def _get_sdd_metadata():
    """
    sdd metadata that is passed through to the Angular app.
    See service-delivery-dashboard.directive.js for an example of using this.
    """
    return {
        SDDSections.PW_LW_CHILDREN: {
            'label': _('PW, LW & Children 0-3 years (0-1095 days)'),
            'image': static('icds_reports/mobile/images/motherandchild.png')
        },
        SDDSections.CHILDREN: {
            'label': _('Children 3-6 years (1096-2190 days)'),
            'image': static('icds_reports/mobile/images/babyboy.png')
        },
    }

@attr.s
class NavMenuSectionsList (object):
    sections = attr.ib()


@attr.s
class NavMenuSection (object):
    name = attr.ib()
    sub_pages = attr.ib()
    sectionId = attr.ib()  # used to collapse and expand a section in nav menu
    icon = attr.ib(default='fa-child')  # used for image of navigation section heading in web
    image = attr.ib(default='mother.png')  # used for image of navigation section heading in mobile


@attr.s
class NavMenuSubPages (object):
    name = attr.ib()
    route = attr.ib()
    featureFlagOnly = attr.ib(default=False)
    showInWeb = attr.ib(default=True)
    showInMobile = attr.ib(default=True)


@attr.s
class FactSheetSectionsList (object):
    sections = attr.ib()


@attr.s
class FactSheetSection (object):
    name = attr.ib()
    route = attr.ib()
    image = attr.ib()
    style = attr.ib()


def _get_factsheet_sections():
    return attr.asdict(FactSheetSectionsList([
        FactSheetSection('Maternal And Child Nutrition',
                         'maternal_and_child_nutrition',
                         'maternal_and_child.png',
                         'fact-sheet-nav-nutrition'),
        FactSheetSection('Interventions',
                         'interventions',
                         'interventions.png',
                         'fact-sheet-nav-interventions'),
        FactSheetSection('Behavior change',
                         'behavior_change',
                         'behavior_change.png',
                         'fact-sheet-nav-behaviour-change'),
        FactSheetSection('Water Sanitation and Hygiene',
                         'water_sanitation_and_hygiene',
                         'water_sanitation_hygiene.png',
                         'fact-sheet-nav-water'),
        FactSheetSection('Demographics',
                         'demographics',
                         'demographics.png',
                         'fact-sheet-nav-demographics'),
        FactSheetSection('All',
                         'all',
                         'all.png',
                         'fact-sheet-nav-all')
    ]))


def _get_nav_menu_items():
    icds_reach_sub_pages = [NavMenuSubPages(_('AWCs Daily Status'), 'icds_cas_reach/awc_daily_status'),
                            NavMenuSubPages(_('AWCs Launched'), 'icds_cas_reach/awcs_covered'),
                            NavMenuSubPages(_('LSs Launched'), 'icds_cas_reach/ls_launched')]
    return attr.asdict(NavMenuSectionsList([
        NavMenuSection(_('Maternal and Child Nutrition'),
                       [NavMenuSubPages(_('Prevalence of Underweight (Weight-for-Age)'),
                                        'maternal_and_child/underweight_children'),
                        NavMenuSubPages(_('Prevalence of Wasting (Weight-for-Height)'),
                                        'maternal_and_child/wasting'),
                        NavMenuSubPages(_('Prevalence of Stunting (Height-for-Age)'),
                                        'maternal_and_child/stunting'),
                        NavMenuSubPages(_('Newborns with Low Birth Weight'),
                                        'maternal_and_child/low_birth'),
                        NavMenuSubPages(_('Early Initiation of Breastfeeding'),
                                        'maternal_and_child/early_initiation'),
                        NavMenuSubPages(_('Exclusive Breastfeeding'),
                                        'maternal_and_child/exclusive_breastfeeding'),
                        NavMenuSubPages(_('Children initiated appropriate complementary feeding'),
                                        'maternal_and_child/children_initiated'),
                        NavMenuSubPages(_('Institutional deliveries'),
                                        'maternal_and_child/institutional_deliveries'),
                        NavMenuSubPages(_('Immunization coverage (at age 1 year)'),
                                        'maternal_and_child/immunization_coverage')],
                       'healthCollapsed', 'fa-child', 'mother.png'
                       ),
        NavMenuSection(_('ICDS-CAS Reach'),
                       icds_reach_sub_pages,
                       'icdsCasReach', 'fa-bar-chart', 'stats-sidebar.png'
                       ),
        NavMenuSection(_('Demographics'),
                       [NavMenuSubPages(_('Registered Households'), 'demographics/registered_household'),
                        NavMenuSubPages(_('Aadhaar-seeded Beneficiaries'), 'demographics/adhaar'),
                        NavMenuSubPages(_('Children enrolled for Anganwadi Services'),
                                        'demographics/enrolled_children'),
                        NavMenuSubPages(_('Pregnant Women enrolled for Anganwadi Services'),
                                        'demographics/enrolled_women'),
                        NavMenuSubPages(_('Lactating Mothers enrolled for Anganwadi Services'),
                                        'demographics/lactating_enrolled_women'),
                        NavMenuSubPages(_('Out of school Adolescent girls (11-14 years)'),
                                        'demographics/adolescent_girls')],
                       'demographics', 'fa-users', 'threegroup-sidebar.png'
                       ),
        NavMenuSection(_('AWC Infrastructure'),
                       [NavMenuSubPages(_('AWCs Reported Clean Drinking Water'),
                                        'awc_infrastructure/clean_water'),
                        NavMenuSubPages(_('AWCs Reported functional toilet'),
                                        'awc_infrastructure/functional_toilet'),
                        NavMenuSubPages(_('AWCs Reported Weighing Scale: Infants'),
                                        'awc_infrastructure/infants_weight_scale'),
                        NavMenuSubPages(_('AWCs Reported Weighing Scale: Mother and Child'),
                                        'awc_infrastructure/adult_weight_scale'),
                        NavMenuSubPages(_('AWCs Reported Medicine kit'),
                                        'awc_infrastructure/medicine_kit'),
                        NavMenuSubPages(_('AWCs Reported Infantometer'),
                                        'awc_infrastructure/infantometer'),
                        NavMenuSubPages(_('AWCs Reported Stadiometer'),
                                        'awc_infrastructure/stadiometer')],
                       'infrastructure', 'fa-lightbulb-o', 'bulb-sidebar.png'
                       ),
    ]))
