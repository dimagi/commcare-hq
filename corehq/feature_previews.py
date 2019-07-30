"""
Feature Previews are built on top of toggle, so if you migrate a toggle to
a feature preview, you shouldn't need to migrate the data, as long as the
slug is kept intact.
"""
from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext_lazy as _
from django_prbac.utils import has_privilege as prbac_has_privilege

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.util.quickcache import quickcache
from .privileges import LOOKUP_TABLES
from .toggles import (
    StaticToggle,
    NAMESPACE_DOMAIN,
    TAG_PREVIEW,
    all_toggles_by_name_in_scope,
    ECD_MIGRATED_DOMAINS,
    ECD_PREVIEW_ENTERPRISE_DOMAINS,
)


class FeaturePreview(StaticToggle):
    """
    FeaturePreviews should be used in conjunction with normal role based access.
    Check the FeaturePreview first since that's a faster operation.

    e.g.

    if feature_previews.BETA_FEATURE.enabled(domain) \
            and has_privilege(request, privileges.BETA_FEATURE):
        # do cool thing for BETA_FEATURE
    """

    def __init__(self, slug, label, description, help_link=None, privilege=None,
                 save_fn=None, can_self_enable_fn=None):
        self.privilege = privilege

        # a function determining whether this preview can be enabled
        # according to the request object
        self.can_self_enable_fn = can_self_enable_fn

        super(FeaturePreview, self).__init__(
            slug, label, TAG_PREVIEW, description=description,
            help_link=help_link, save_fn=save_fn, namespaces=[NAMESPACE_DOMAIN]
        )

    def has_privilege(self, request):
        has_privilege = True
        if self.privilege:
            has_privilege = prbac_has_privilege(request, self.privilege)

        can_self_enable = True
        if self.can_self_enable_fn:
            can_self_enable = self.can_self_enable_fn(request)

        return has_privilege and can_self_enable


@quickcache([])
def all_previews():
    return list(all_toggles_by_name_in_scope(globals()).values())


def all_previews_by_name():
    return all_toggles_by_name_in_scope(globals())


@quickcache(['domain'])
def previews_dict(domain):
    return {t.slug: True for t in all_previews() if t.enabled(domain)}


def preview_values_by_name(domain):
    return {toggle_name: toggle.enabled(domain)
            for toggle_name, toggle in all_previews_by_name().items()}


CALC_XPATHS = FeaturePreview(
    slug='calc_xpaths',
    label=_('Custom Calculations in Case List'),
    description=_(
        "Specify a custom xpath expression to calculate a value "
        "in the case list or case detail screen."),
    help_link='https://confluence.dimagi.com/display/commcarepublic/Calculations+in+the+Case+List+and+Details'
)

ENUM_IMAGE = FeaturePreview(
    slug='enum_image',
    label=_('Icons in Case List'),
    description=_(
        "Display a case property as an icon in the case list. "
        "For example, to show that a case is late, "
        'display a red square instead of "late: yes".'
    ),
    help_link='https://help.commcarehq.org/display/commcarepublic/Adding+Icons+in+Case+List+and+Case+Detail+screen'
)

CONDITIONAL_ENUM = FeaturePreview(
    slug='conditional_enum',
    label=_('Conditional ID Mapping in Case List'),
    description=_(
        "Specify a custom xpath expression to calculate a lookup key in the case list, case detail screen or "
        "case tile enum columns."
    ),
)

SPLIT_MULTISELECT_CASE_EXPORT = FeaturePreview(
    slug='split_multiselect_case_export',
    label=_('Split multi-selects in case export'),
    description=_(
        "This setting allows users to split multi-select questions into multiple "
        "columns in case exports."
    )
)


def enable_callcenter(domain_name, checked):
    from corehq.apps.domain.models import Domain
    domain_obj = Domain.get_by_name(domain_name)
    domain_obj.call_center_config.enabled = checked
    domain_obj.save()


def can_enable_callcenter(request):
    # This will only allow domains to remove themselves from the
    # call center feature preview, but no new domains can currently activate
    # the preview. A request from product
    return CALLCENTER.enabled_for_request(request)


CALLCENTER = FeaturePreview(
    slug='callcenter',
    label=_("Call Center"),
    description=_(
        'The call center application setting allows an application to reference a '
        'mobile user as a case that can be monitored using CommCare.  '
        'This allows supervisors to view their workforce within CommCare.  '
        'From here they can do things like monitor workers with performance issues, '
        'update their case with possible reasons for poor performance, '
        'and offer guidance towards solutions.'),
    help_link='https://help.commcarehq.org/display/commcarepublic/How+to+set+up+a+Supervisor-Call+Center+Application',
    save_fn=enable_callcenter,
    can_self_enable_fn=can_enable_callcenter,
)


# Only used in Vellum
VELLUM_ADVANCED_ITEMSETS = FeaturePreview(
    slug='advanced_itemsets',
    label=_("Custom Single and Multiple Answer Questions"),
    description=_(
        "Allows display of custom lists, such as case sharing groups or locations as choices in Single Answer or "
        "Multiple Answer lookup Table questions. Configuring these questions requires specifying advanced logic. "
        "Available in form builder, as an additional option on the Lookup Table Data for lookup "
        "table questions."
    ),
    privilege=LOOKUP_TABLES,
)


def is_eligible_for_ecd_preview(request):
    if not (hasattr(request, 'plan')
            and hasattr(request, 'subscription')
            and hasattr(request, 'domain')):
        return False

    if request.subscription.is_trial:
        return False

    is_migrated = ECD_MIGRATED_DOMAINS.enabled_for_request(request)
    is_enterprise_eligible = ECD_PREVIEW_ENTERPRISE_DOMAINS.enabled_for_request(request)
    is_pro_or_advanced = request.plan.plan.edition in [
        SoftwarePlanEdition.ADVANCED,
        SoftwarePlanEdition.PRO
    ]

    return is_migrated and (is_pro_or_advanced or is_enterprise_eligible)


def clear_project_data_tab_cache(domain_name, _checked):
    from corehq.tabs.tabclasses import ProjectDataTab
    ProjectDataTab.clear_dropdown_cache_for_all_domain_users(domain_name)


EXPLORE_CASE_DATA_PREVIEW = FeaturePreview(
    slug='explore_case_data_preview',
    label=_("Explore Case Data"),
    description=_(
        "This feature allows you to quickly explore your case data for "
        "ad-hoc data queries or to identify unclean data."
    ),
    can_self_enable_fn=is_eligible_for_ecd_preview,
    save_fn=clear_project_data_tab_cache,
)
