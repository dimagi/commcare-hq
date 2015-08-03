"""
Feature Previews are built on top of toggle, so if you migrate a toggle to
a feature preview, you shouldn't need to migrate the data, as long as the
slug is kept intact.
"""
from django.utils.translation import ugettext_lazy as _
from corehq.toggles import TAG_PREVIEW
from django_prbac.utils import has_privilege as prbac_has_privilege

from .toggles import StaticToggle, NAMESPACE_DOMAIN


class FeaturePreview(StaticToggle):
    """
    FeaturePreviews should be used in conjunction with normal role based access.
    Check the FeaturePreview first since that's a faster operation.

    e.g.

    if feature_previews.BETA_FEATURE.enabled(domain) \
            and has_privilege(request, privileges.BETA_FEATURE):
        # do cool thing for BETA_FEATURE
    """
    def __init__(self, slug, label, description, help_link=None, privilege=None, save_fn=None):
        self.privilege = privilege
        self.save_fn = save_fn
        super(FeaturePreview, self).__init__(slug, label, TAG_PREVIEW, description=description, help_link=help_link,
                                             namespaces=[NAMESPACE_DOMAIN])

    def has_privilege(self, request):
        if not self.privilege:
            return True

        return prbac_has_privilege(request, self.privilege)


SUBMIT_HISTORY_FILTERS = FeaturePreview(
    slug='submit_history_filters',
    label=_("Advanced Submit History Filters"),
    description=_("Filter the forms in the Submit History report by data in "
        "the form submissions. Add extra columns to the report that represent "
        "data in the forms."),
    # privilege=privileges.
    # help_link='https://confluence.dimagi.com/display/SPEC/Feature+Preiview+aka+Labs+Specification'
)

CALC_XPATHS = FeaturePreview(
    slug='calc_xpaths',
    label=_('Custom Calculations in Case List'),
    description=_(
        "Specify a custom xpath expression to calculate a value "
        "in the case list or case detail screen."),
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

SPLIT_MULTISELECT_CASE_EXPORT = FeaturePreview(
    slug='split_multiselect_case_export',
    label=_('Split multi-selects in case export'),
    description=_(
        "This setting allows users to split multi-select questions into multiple "
        "columns in case exports."
    )
)


def enable_commtrack_previews(domain):
    for toggle_class in [COMMTRACK, LOCATIONS]:
        toggle_class.set(domain.name, True, NAMESPACE_DOMAIN)


def commtrackify(domain_name, checked):
    from corehq.apps.domain.models import Domain
    domain = Domain.get_by_name(domain_name)
    domain.commtrack_enabled = checked
    if checked:
        enable_commtrack_previews(domain)
    domain.save()

COMMTRACK = FeaturePreview(
    slug='commtrack',
    label=_("CommCare Supply"),
    description=_(
        '<a href="http://www.commtrack.org/home/">CommCare Supply</a> '
        "is a logistics and supply chain management module. It is designed "
        "to improve the management, transport, and resupply of a variety of "
        "goods and materials, from medication to food to bednets. <br/>"
        "Note: You must also enable CommCare Supply on any CommCare Supply "
        "application's settings page."),
    help_link='https://help.commcarehq.org/display/commtrack/CommCare+Supply+Home',
    save_fn=commtrackify,
)


def enable_callcenter(domain_name, checked):
    from corehq.apps.domain.models import Domain
    domain = Domain.get_by_name(domain_name)
    domain.call_center_config.enabled = checked
    domain.save()


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


LOCATIONS = FeaturePreview(
    slug='locations',
    label=_("Locations"),
    description=_(
        'Enable locations for this project. This must be enabled for '
        'CommCare Supply to work properly'
    ),
    help_link='https://help.commcarehq.org/display/commtrack/Locations',
)

MODULE_FILTER = FeaturePreview(
    slug='module_filter',
    label=_('Module Filtering'),
    description=_(
        'Similar to form display conditions, hide your module unless the condition is met. Most commonly used'
        ' in conjunction with '
        '<a href="https://help.commcarehq.org/display/commcarepublic/Custom+User+Data">custom user data</a>.'
    ),
)
