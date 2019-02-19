"""
Feature Previews are built on top of toggle, so if you migrate a toggle to
a feature preview, you shouldn't need to migrate the data, as long as the
slug is kept intact.
"""
from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext_lazy as _
from django_prbac.utils import has_privilege as prbac_has_privilege

from corehq.util.quickcache import quickcache
from .privileges import LOOKUP_TABLES
from .toggles import StaticToggle, NAMESPACE_DOMAIN, TAG_PREVIEW, \
    all_toggles_by_name_in_scope


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
                 save_fn=None):
        self.privilege = privilege
        super(FeaturePreview, self).__init__(
            slug, label, TAG_PREVIEW, description=description,
            help_link=help_link, save_fn=save_fn, namespaces=[NAMESPACE_DOMAIN]
        )

    def has_privilege(self, request):
        if not self.privilege:
            return True

        return prbac_has_privilege(request, self.privilege)


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
